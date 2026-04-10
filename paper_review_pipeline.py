#!/usr/bin/env python3
"""Async producer-consumer pipeline for Claude analysis and Codex review."""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import os
import pathlib
import re
import signal
import sys
import time
from dataclasses import dataclass
from json import JSONDecoder
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SURVEY_ROOT = REPO_ROOT / "workspace" / "survey"
DEFAULT_TOPIC = "cpu-ai"
CLAUDE_COMMAND_NAME = "analyze-paper-claude"
CODEX_REVIEW_SCRIPT = (
    SURVEY_ROOT / "skill" / "codex" / "paper-json-review" / "scripts" / "run_codex_review.sh"
)


def default_dirs(topic: str) -> dict[str, pathlib.Path]:
    """Compute default directories for a given topic."""
    corpus = SURVEY_ROOT / "data" / "topics" / topic / "corpus"
    return {
        "corpus": corpus / "draft",
        "analysis": corpus / "llm" / "glm5.1",
        "review": corpus / "llm" / "gpt5.4",
        "logs": corpus / "paper_review_pipeline",
        "runs": corpus / "paper_review_pipeline",
    }


@dataclass(frozen=True)
class PaperJob:
    paper_json: pathlib.Path
    analysis_json: pathlib.Path
    review_json: pathlib.Path
    revised_json: pathlib.Path

    @property
    def stem(self) -> str:
        return self.paper_json.stem


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--topic",
        default=DEFAULT_TOPIC,
        help=f"Topic directory name under data/topics/ (default: {DEFAULT_TOPIC}).",
    )
    parser.add_argument(
        "--papers",
        nargs="*",
        help="Explicit paper JSON paths. If omitted, select from corpus by --limit.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Number of corpus papers to process when --papers is omitted. If omitted, process all corpus papers.",
    )
    # Pre-parse to get topic for defaults
    _known = parser.parse_known_args()[0]
    _dirs = default_dirs(_known.topic)

    parser.add_argument(
        "--analysis-dir",
        type=pathlib.Path,
        default=_dirs["analysis"],
        help="Directory for Claude-generated dossier JSON files.",
    )
    parser.add_argument(
        "--review-dir",
        type=pathlib.Path,
        default=_dirs["review"],
        help="Directory for Codex review/revised JSON files.",
    )
    parser.add_argument(
        "--log-dir",
        type=pathlib.Path,
        default=_dirs["logs"],
        help="Directory where Claude/Codex command logs will be written.",
    )
    parser.add_argument(
        "--status-dir",
        type=pathlib.Path,
        default=_dirs["logs"] / "status",
        help="Directory where per-paper stage status JSON files will be written.",
    )
    parser.add_argument(
        "--claude-cmd",
        default="claude",
        help="Claude CLI executable.",
    )
    parser.add_argument(
        "--claude-model",
        default="",
        help="Optional Claude model alias/name for generation.",
    )
    parser.add_argument(
        "--codex-review-script",
        type=pathlib.Path,
        default=CODEX_REVIEW_SCRIPT,
        help="Wrapper script that runs the paper-json-review skill.",
    )
    parser.add_argument(
        "--queue-size",
        type=int,
        default=1,
        help="Queue size between Claude generation and Codex review.",
    )
    parser.add_argument(
        "--strict-serial",
        action="store_true",
        help="Disable producer-consumer overlap and force full one-paper-at-a-time execution.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Reuse existing JSON artifacts when present and parseable.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print commands without executing remote model calls.",
    )
    parser.add_argument(
        "--summary-file",
        type=pathlib.Path,
        default=_dirs["runs"] / "latest" / "summary.json",
        help="Where to write the pipeline run summary JSON.",
    )
    parser.add_argument(
        "--claude-timeout-sec",
        type=int,
        default=1800,
        help="Timeout in seconds for one Claude generation job.",
    )
    parser.add_argument(
        "--codex-timeout-sec",
        type=int,
        default=3600,
        help="Timeout in seconds for one Codex review job.",
    )
    parser.add_argument(
        "--heartbeat-sec",
        type=int,
        default=15,
        help="How often to refresh the running status heartbeat file.",
    )
    parser.add_argument(
        "--run-id",
        default="latest",
        help="Run identifier used under workspace/scripts/runs/paper_review_pipeline/.",
    )
    parser.add_argument(
        "--corpus-dir",
        type=pathlib.Path,
        default=None,
        help="Override corpus draft directory (auto-derived from --topic if omitted).",
    )
    parser.add_argument(
        "--retry-failed-from",
        type=pathlib.Path,
        default=None,
        help="Path to a previous run summary.json or failed_papers.json. Only failed papers from that batch will be retried.",
    )
    parser.add_argument(
        "--claude-max-retries",
        type=int,
        default=2,
        help="Maximum retries for one Claude job on retryable failures.",
    )
    parser.add_argument(
        "--codex-max-retries",
        type=int,
        default=3,
        help="Maximum retries for one Codex job on retryable failures.",
    )
    parser.add_argument(
        "--retry-backoff-sec",
        type=int,
        default=60,
        help="Base backoff in seconds between retries for retryable failures.",
    )
    parser.add_argument(
        "--codex-stop-after-consecutive-failures",
        type=int,
        default=3,
        help="Stop the batch after this many consecutive Codex backend/retryable failures.",
    )
    return parser.parse_args()


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_valid_json_file(path: pathlib.Path) -> bool:
    try:
        load_json(path)
        return True
    except Exception:
        return False


def extract_first_json_object(text: str) -> dict[str, Any]:
    decoder = JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            obj, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj
    raise ValueError("Could not locate a JSON object in Claude output.")


def select_papers(args: argparse.Namespace) -> list[pathlib.Path]:
    if args.retry_failed_from:
        payload = json.loads(args.retry_failed_from.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "failed_papers" in payload:
            papers = [pathlib.Path(p).resolve() for p in payload["failed_papers"]]
        elif isinstance(payload, dict) and "summary" in payload:
            papers = [
                pathlib.Path(item["paper_json"]).resolve()
                for item in payload["summary"]
                if item.get("analysis_status") == "failed" or item.get("review_status") == "failed"
            ]
        else:
            raise ValueError("Unsupported --retry-failed-from payload.")
        if args.limit is not None:
            papers = papers[: args.limit]
        return papers

    if args.papers:
        papers = [pathlib.Path(p).expanduser().resolve() for p in args.papers]
    else:
        corpus_dir = getattr(args, "corpus_dir", None) or default_dirs(args.topic)["corpus"]
        args.corpus_dir = corpus_dir
        corpus_files = sorted(
            path
            for path in corpus_dir.glob("*.json")
            if path.name != "index.json"
        )
        papers = corpus_files if args.limit is None else corpus_files[: args.limit]
    if args.limit is not None and args.papers:
        papers = papers[: args.limit]
    return papers


def build_jobs(args: argparse.Namespace) -> list[PaperJob]:
    jobs: list[PaperJob] = []
    args.analysis_dir.mkdir(parents=True, exist_ok=True)
    args.review_dir.mkdir(parents=True, exist_ok=True)
    args.log_dir.mkdir(parents=True, exist_ok=True)
    args.status_dir.mkdir(parents=True, exist_ok=True)
    for paper in select_papers(args):
        stem = paper.stem
        jobs.append(
            PaperJob(
                paper_json=paper,
                analysis_json=args.analysis_dir / f"{stem}.json",
                review_json=args.review_dir / f"{stem}.review.json",
                revised_json=args.review_dir / f"{stem}.revised.json",
            )
        )
    return jobs


def classify_failure(returncode: int, stdout: str, stderr: str) -> tuple[str, bool]:
    text = f"{stderr}\n{stdout}".lower()
    retryable_patterns = [
        r"\b429\b",
        r"rate limit",
        r"too many requests",
        r"insufficient_quota",
        r"quota",
        r"capacity",
        r"temporarily unavailable",
        r"503 service unavailable",
        r"service unavailable",
        r"currently experiencing high demand",
        r"stream disconnected",
        r"timeout",
        r"timed out",
        r"connection reset",
        r"econnreset",
        r"service unavailable",
    ]
    fatal_patterns = [
        r"invalid_api_key",
        r"incorrect api key",
        r"unauthorized",
        r"missing bearer",
        r"permission denied",
        r"no such file or directory",
    ]

    for pat in fatal_patterns:
        if re.search(pat, text):
            return pat, False
    for pat in retryable_patterns:
        if re.search(pat, text):
            return pat, True
    return f"exit_code_{returncode}", False


def stage_log_paths(args: argparse.Namespace, job: PaperJob, stage: str) -> dict[str, pathlib.Path]:
    stage_dir = args.log_dir / stage
    stage_dir.mkdir(parents=True, exist_ok=True)
    return {
        "cmd": stage_dir / f"{job.stem}.cmd.txt",
        "stdout": stage_dir / f"{job.stem}.stdout.log",
        "stderr": stage_dir / f"{job.stem}.stderr.log",
    }


def write_text(path: pathlib.Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def status_file_path(args: argparse.Namespace, job: PaperJob, stage: str) -> pathlib.Path:
    return args.status_dir / f"{job.stem}.{stage}.status.json"


def write_status(
    path: pathlib.Path,
    payload: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_stage_logs(
    paths: dict[str, str],
    command: list[str],
    stdout: str,
    stderr: str,
) -> None:
    write_text(pathlib.Path(paths["cmd"]), " ".join(command) + "\n")
    write_text(pathlib.Path(paths["stdout"]), stdout)
    write_text(pathlib.Path(paths["stderr"]), stderr)


async def run_command(
    cmd: list[str],
    *,
    cwd: pathlib.Path,
    status_path: pathlib.Path,
    stage: str,
    job_name: str,
    timeout_sec: int,
    heartbeat_sec: int,
    env: dict[str, str] | None = None,
) -> tuple[int, str, str]:
    process = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(cwd),
        env=env,
        start_new_session=True,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    started = time.time()
    write_status(
        status_path,
        {
            "stage": stage,
            "job_name": job_name,
            "state": "running",
            "pid": process.pid,
            "started_at_unix": started,
            "elapsed_sec": 0,
            "timeout_sec": timeout_sec,
            "cwd": str(cwd),
            "command": cmd,
        },
    )

    async def heartbeat_task() -> None:
        while process.returncode is None:
            await asyncio.sleep(max(heartbeat_sec, 1))
            if process.returncode is not None:
                break
            write_status(
                status_path,
                {
                    "stage": stage,
                    "job_name": job_name,
                    "state": "running",
                    "pid": process.pid,
                    "started_at_unix": started,
                    "elapsed_sec": round(time.time() - started, 2),
                    "timeout_sec": timeout_sec,
                    "cwd": str(cwd),
                    "command": cmd,
                },
            )

    hb = asyncio.create_task(heartbeat_task())
    timed_out = False
    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout_sec,
        )
    except asyncio.TimeoutError:
        timed_out = True
        with contextlib.suppress(ProcessLookupError):
            os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=10,
            )
        except asyncio.TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            stdout_bytes, stderr_bytes = await process.communicate()
    finally:
        hb.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await hb

    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    write_status(
        status_path,
        {
            "stage": stage,
            "job_name": job_name,
            "state": "timeout" if timed_out else "finished",
            "pid": process.pid,
            "started_at_unix": started,
            "finished_at_unix": time.time(),
            "elapsed_sec": round(time.time() - started, 2),
            "timeout_sec": timeout_sec,
            "returncode": process.returncode,
            "stdout_tail": stdout_text[-4000:],
            "stderr_tail": stderr_text[-4000:],
        },
    )
    if timed_out:
        stderr_text = (
            stderr_text
            + f"\n[paper_review_pipeline] process timed out after {timeout_sec} seconds.\n"
        )
        return 124, stdout_text, stderr_text

    return process.returncode, stdout_text, stderr_text


def claude_command(job: PaperJob, args: argparse.Namespace) -> list[str]:
    command = [
        args.claude_cmd,
        "-p",
        f"/{CLAUDE_COMMAND_NAME} {job.paper_json}",
        "--output-format",
        "text",
        "--no-session-persistence",
        "--allowedTools",
        "Read,Grep,Glob,Bash",
        "--add-dir",
        str(SURVEY_ROOT),
    ]
    if args.claude_model:
        command.extend(["--model", args.claude_model])
    return command


def codex_command(job: PaperJob, args: argparse.Namespace) -> list[str]:
    return [
        "bash",
        str(args.codex_review_script),
        str(job.analysis_json),
        str(job.paper_json),
        str(args.review_dir),
    ]


async def producer(
    jobs: list[PaperJob],
    queue: asyncio.Queue[PaperJob | None],
    ack_queue: asyncio.Queue[str],
    args: argparse.Namespace,
    summary: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    stop_event: asyncio.Event,
) -> None:
    for job in jobs:
        if stop_event.is_set():
            break
        record: dict[str, Any] = {
            "paper_json": str(job.paper_json),
            "analysis_json": str(job.analysis_json),
            "review_json": str(job.review_json),
            "revised_json": str(job.revised_json),
            "claude_log_dir": str(args.log_dir / "claude"),
            "codex_log_dir": str(args.log_dir / "codex"),
            "analysis_status": "pending",
            "review_status": "pending",
        }
        summary.append(record)
        records[str(job.paper_json)] = record

        if args.skip_existing and is_valid_json_file(job.analysis_json):
            record["analysis_status"] = "reused"
            print(f"[claude] reuse {job.analysis_json}")
            await queue.put(job)
            if args.strict_serial:
                await ack_queue.get()
            continue

        command = claude_command(job, args)
        record["claude_command"] = command
        print(f"[claude] generate {job.paper_json.name}")
        if args.dry_run:
            record["analysis_status"] = "dry_run"
            record["analysis_stdout_preview"] = " ".join(command)
            await queue.put(job)
            if args.strict_serial:
                await ack_queue.get()
            continue

        record["analysis_logs"] = {
            key: str(value)
            for key, value in stage_log_paths(args, job, "claude").items()
        }
        record["analysis_status_file"] = str(status_file_path(args, job, "claude"))
        stdout = ""
        stderr = ""
        returncode = 1
        failure_kind = "unknown"
        for attempt in range(args.claude_max_retries + 1):
            record["analysis_attempt"] = attempt + 1
            started = time.time()
            returncode, stdout, stderr = await run_command(
                command,
                cwd=REPO_ROOT,
                status_path=status_file_path(args, job, "claude"),
                stage="claude",
                job_name=job.paper_json.name,
                timeout_sec=args.claude_timeout_sec,
                heartbeat_sec=args.heartbeat_sec,
            )
            failure_kind, retryable = classify_failure(returncode, stdout, stderr)
            if returncode == 0:
                break
            if attempt < args.claude_max_retries and retryable:
                sleep_sec = args.retry_backoff_sec * (attempt + 1)
                print(f"[claude] retryable failure ({failure_kind}), retry in {sleep_sec}s: {job.paper_json.name}")
                await asyncio.sleep(sleep_sec)
                continue
            break
        write_stage_logs(record["analysis_logs"], command, stdout, stderr)
        record["analysis_duration_sec"] = round(time.time() - started, 2)
        record["analysis_returncode"] = returncode
        if stderr.strip():
            record["analysis_stderr"] = stderr[-8000:]
        if returncode != 0:
            record["analysis_status"] = "failed"
            record["analysis_error"] = f"Claude command failed with exit code {returncode}."
            record["analysis_failure_kind"] = failure_kind
            print(f"[claude] failed {job.paper_json.name}")
            print(f"         stderr -> {record['analysis_logs']['stderr']}")
            continue

        try:
            obj = extract_first_json_object(stdout)
            job.analysis_json.write_text(
                json.dumps(obj, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            record["analysis_status"] = "failed"
            record["analysis_error"] = str(exc)
            record["analysis_stdout_preview"] = stdout[:4000]
            print(f"[claude] invalid-json {job.paper_json.name}")
            print(f"         stdout -> {record['analysis_logs']['stdout']}")
            continue

        record["analysis_status"] = "completed"
        print(f"[claude] done {job.analysis_json.name}")
        print(f"         output -> {job.analysis_json}")
        print(f"         logs   -> {record['analysis_logs']['stdout']} | {record['analysis_logs']['stderr']}")
        await queue.put(job)
        if args.strict_serial:
            await ack_queue.get()

    await queue.put(None)


async def consumer(
    queue: asyncio.Queue[PaperJob | None],
    ack_queue: asyncio.Queue[str],
    args: argparse.Namespace,
    summary: list[dict[str, Any]],
    records: dict[str, dict[str, Any]],
    stop_event: asyncio.Event,
) -> None:
    consecutive_retryable_failures = 0
    while True:
        job = await queue.get()
        if job is None:
            queue.task_done()
            break

        record = records[str(job.paper_json)]
        if record.get("analysis_status") not in {"completed", "reused", "dry_run"}:
            record["review_status"] = "skipped"
            queue.task_done()
            continue

        if args.skip_existing and is_valid_json_file(job.review_json) and is_valid_json_file(job.revised_json):
            record["review_status"] = "reused"
            print(f"[codex] reuse {job.review_json.name} / {job.revised_json.name}")
            if args.strict_serial:
                await ack_queue.put(job.stem)
            queue.task_done()
            continue

        command = codex_command(job, args)
        record["codex_command"] = command
        print(f"[codex] review {job.analysis_json.name}")
        if args.dry_run:
            record["review_status"] = "dry_run"
            if args.strict_serial:
                await ack_queue.put(job.stem)
            queue.task_done()
            continue

        record["review_logs"] = {
            key: str(value)
            for key, value in stage_log_paths(args, job, "codex").items()
        }
        record["review_status_file"] = str(status_file_path(args, job, "codex"))
        stdout = ""
        stderr = ""
        returncode = 1
        failure_kind = "unknown"
        for attempt in range(args.codex_max_retries + 1):
            record["review_attempt"] = attempt + 1
            started = time.time()
            returncode, stdout, stderr = await run_command(
                command,
                cwd=REPO_ROOT,
                status_path=status_file_path(args, job, "codex"),
                stage="codex",
                job_name=job.analysis_json.name,
                timeout_sec=args.codex_timeout_sec,
                heartbeat_sec=args.heartbeat_sec,
            )
            failure_kind, retryable = classify_failure(returncode, stdout, stderr)
            if returncode == 0:
                break
            if attempt < args.codex_max_retries and retryable:
                sleep_sec = args.retry_backoff_sec * (attempt + 1)
                print(f"[codex] retryable failure ({failure_kind}), retry in {sleep_sec}s: {job.analysis_json.name}")
                await asyncio.sleep(sleep_sec)
                continue
            break
        write_stage_logs(record["review_logs"], command, stdout, stderr)
        record["review_duration_sec"] = round(time.time() - started, 2)
        record["review_returncode"] = returncode
        if stdout.strip():
            record["review_stdout_tail"] = stdout[-4000:]
        if stderr.strip():
            record["review_stderr_tail"] = stderr[-8000:]

        if returncode != 0:
            record["review_status"] = "failed"
            record["review_error"] = f"Codex review wrapper failed with exit code {returncode}."
            record["review_failure_kind"] = failure_kind
            print(f"[codex] failed {job.analysis_json.name}")
            print(f"        stderr -> {record['review_logs']['stderr']}")
            retryable_failure = failure_kind not in {
                "invalid_api_key",
                "incorrect api key",
                "unauthorized",
                "missing bearer",
                "permission denied",
                "no such file or directory",
            } and (
                "quota" in failure_kind
                or "rate limit" in failure_kind
                or "429" in failure_kind
                or "capacity" in failure_kind
                or "high demand" in failure_kind
                or "service unavailable" in failure_kind
                or "stream disconnected" in failure_kind
                or "timeout" in failure_kind
                or failure_kind.startswith("exit_code_124")
            )
            if retryable_failure:
                consecutive_retryable_failures += 1
                if consecutive_retryable_failures >= args.codex_stop_after_consecutive_failures:
                    stop_event.set()
                    print(
                        "[codex] stopping batch after "
                        f"{consecutive_retryable_failures} consecutive retryable backend failures."
                    )
            else:
                consecutive_retryable_failures = 0
            if args.strict_serial:
                await ack_queue.put(job.stem)
            queue.task_done()
            continue

        if not is_valid_json_file(job.review_json) or not is_valid_json_file(job.revised_json):
            record["review_status"] = "failed"
            record["review_error"] = "Expected review/revised JSON files were not created or are invalid."
            print(f"[codex] invalid-output {job.analysis_json.name}")
            print(f"        stdout -> {record['review_logs']['stdout']}")
            if args.strict_serial:
                await ack_queue.put(job.stem)
            queue.task_done()
            continue

        record["review_status"] = "completed"
        consecutive_retryable_failures = 0
        print(f"[codex] done {job.review_json.name} / {job.revised_json.name}")
        print(f"        output -> {job.review_json}")
        print(f"        output -> {job.revised_json}")
        print(f"        logs   -> {record['review_logs']['stdout']} | {record['review_logs']['stderr']}")
        if args.strict_serial:
            await ack_queue.put(job.stem)
        queue.task_done()


def write_summary(path: pathlib.Path, summary: list[dict[str, Any]]) -> None:
    failed_papers = [
        entry["paper_json"]
        for entry in summary
        if entry.get("analysis_status") == "failed" or entry.get("review_status") == "failed"
    ]
    payload = {
        "generated_at_unix": int(time.time()),
        "summary": summary,
        "failed_papers": failed_papers,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed_json = path.parent / "failed_papers.json"
    failed_txt = path.parent / "failed_papers.txt"
    failed_json.write_text(
        json.dumps({"failed_papers": failed_papers}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    failed_txt.write_text("\n".join(failed_papers) + ("\n" if failed_papers else ""), encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    _dirs = default_dirs(args.topic)
    if args.run_id:
        run_root = _dirs["runs"] / args.run_id
        args.summary_file = run_root / "summary.json"
    # Ensure corpus_dir is set
    if not getattr(args, "corpus_dir", None):
        args.corpus_dir = _dirs["corpus"]
    jobs = build_jobs(args)
    if not jobs:
        print("No papers selected.", file=sys.stderr)
        return 2

    print(f"Selected {len(jobs)} paper(s).")
    mode = "strict-serial" if args.strict_serial else "pipelined-1x1"
    print(f"Mode: {mode}")
    print(f"Corpus dir:   {args.corpus_dir}")
    print(f"Topic:        {args.topic}")
    print(f"Claude dir:   {args.analysis_dir}")
    print(f"Codex dir:    {args.review_dir}")
    print(f"Log dir:      {args.log_dir}")
    print(f"Status dir:   {args.status_dir}")
    print(f"Summary file: {args.summary_file}")
    print(f"Run id:       {args.run_id}")
    if args.retry_failed_from:
        print(f"Retry from:   {args.retry_failed_from}")
    for job in jobs:
        print(f"  - {job.paper_json.name}")
        print(f"    paper   -> {job.paper_json}")
        print(f"    claude  -> {job.analysis_json}")
        print(f"    review  -> {job.review_json}")
        print(f"    revised -> {job.revised_json}")

    queue: asyncio.Queue[PaperJob | None] = asyncio.Queue(maxsize=max(args.queue_size, 1))
    ack_queue: asyncio.Queue[str] = asyncio.Queue()
    stop_event = asyncio.Event()
    summary: list[dict[str, Any]] = []
    records: dict[str, dict[str, Any]] = {}

    producer_task = asyncio.create_task(producer(jobs, queue, ack_queue, args, summary, records, stop_event))
    consumer_task = asyncio.create_task(consumer(queue, ack_queue, args, summary, records, stop_event))

    await asyncio.gather(producer_task, consumer_task)
    write_summary(args.summary_file, summary)

    failed = [
        entry
        for entry in summary
        if entry.get("analysis_status") == "failed" or entry.get("review_status") == "failed"
    ]
    print(f"Summary written to {args.summary_file}")
    if failed:
        print(f"Pipeline finished with {len(failed)} failed paper(s).", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    args = parse_args()
    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
