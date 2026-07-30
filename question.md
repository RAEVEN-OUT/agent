PASS  thanks                          free      0ms
{"event": "agent_call_failed", "round": 1, "error": "400 INVALID_ARGUMENT. {'error': {'code': 400, 'message': 'Function call is missing a thought_signature in functionCall parts. This is required for tools to work correctly, and missing thought_signature may lead to degraded model performance. Additional data, function call `default_api:search_catalog", "level": "ERROR", "logger": "agent.loop"}
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/app/scripts/eval_harness.py", line 245, in <module>
    asyncio.run(main())
  File "/usr/local/lib/python3.12/asyncio/runners.py", line 195, in run
    return runner.run(main)
           ^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/asyncio/runners.py", line 118, in run
    return self._loop.run_until_complete(task)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/local/lib/python3.12/asyncio/base_events.py", line 691, in run_until_complete
    return future.result()
           ^^^^^^^^^^^^^^^
  File "/app/scripts/eval_harness.py", line 177, in main
    outcome = await process_message(
              ^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/pipeline/orchestrator.py", line 410, in process_message
    result = await catalog_qa.handle(
             ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/modules/catalog_qa.py", line 235, in handle
    found.facts_block(currency),
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/app/app/modules/hybrid_retrieval.py", line 96, in facts_block
    f"- PRODUCT {p.get('name')}{size}: {currency} {p.get('price'):.0f}, "
                                                  ^^^^^^^^^^^^^^^^^^^^
TypeError: unsupported format string passed to NoneType.__format__

What's next:
    Debug this Compose error with Gordon → docker ai "help me fix this compose error"
PS D:\Projects\agent\whatsapp-ai-employee> 