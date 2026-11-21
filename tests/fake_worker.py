"""Stand-in worker that speaks the protocol: input 'sleep' blocks, 'crash' dies, anything else succeeds."""
import os
import sys
import time

from musicmultitool.core.protocol import Done, Output, decode_job, encode_event

for line in sys.stdin:
    job = decode_job(line)
    if job.input == "crash":
        print("fake: out of memory", file=sys.stderr, flush=True)
        os._exit(1)
    if job.input == "garbage":
        print("1", flush=True)  # valid JSON, not an event
    if job.input == "sleep":
        time.sleep(60)
    print(encode_event(Done(job.id, (Output("audio", "/x"),), {})), flush=True)
