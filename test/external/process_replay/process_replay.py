#!/usr/bin/env python3
# compare kernels created by HEAD against master
import difflib, pickle
from tinygrad.codegen.linearizer import Linearizer
from tinygrad.helpers import Context, ContextVar, colored, db_connection, VERSION, getenv, tqdm

class ProcessReplayError(Exception): pass

page_size = 100
conn = db_connection()
cur = conn.cursor()
row_count = cur.execute(f"select count(*) from 'process_replay_{VERSION}'").fetchone()[0]
for offset in tqdm(range(0, row_count, page_size)):
  cur.execute(f"SELECT val FROM 'process_replay_{VERSION}' LIMIT ? OFFSET ?", (page_size, offset))
  for row in cur.fetchall():
    ast, opts, applied_opts, name, compare_src, ctx = pickle.loads(row[0])
    with Context(**{k:v for k,v in ctx.items() if k in ContextVar._cache}):
      try:
        k = Linearizer(*ast, opts=opts)
        for opt in applied_opts: k.apply_opt(opt)
        good_src = k.opts.render(name, k.linearize().uops)
        try: assert compare_src == good_src
        except AssertionError:
          print("PROCESS REPLAY DETECTED CHANGE")
          print(ast)
          print(applied_opts)
          diff = list(difflib.unified_diff(good_src.splitlines(), compare_src.splitlines()))
          for line in diff:
            print(colored(line, "red" if line.startswith("-") else "green" if line.startswith("+") else None))
          if getenv("ASSERT_PROCESS_REPLAY", 1): raise ProcessReplayError()
      except ProcessReplayError as e: raise e
      except Exception as e:
        print("FAILED TO RECREATE KERNEL")
        print(ast)
        print(applied_opts)
        print(e)
        if getenv("ASSERT_PROCESS_REPLAY", 1): raise e
