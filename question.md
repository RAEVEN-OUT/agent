PS D:\Projects\agent\whatsapp-ai-employee> docker compose logs api -f
api-1  | INFO:     Started server process [1]
api-1  | {"event": "startup", "env": "dev", "level": "INFO", "logger": "main"}
api-1  | INFO:     Waiting for application startup.
api-1  | {"event": "tables_ready", "level": "INFO", "logger": "main"}
api-1  | INFO:     Application startup complete.
api-1  | INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)  
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "hi", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.62, "guardrails": 0.01, "smalltalk": 0.03}, "trace": {"path": "smalltalk"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51046 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQjdBRDQ5NkY5MzM3NjcwQjlFAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51062 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQjdBRDQ5NkY5MzM3NjcwQjlFAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51070 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQjdBRDQ5NkY5MzM3NjcwQjlFAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51084 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "hi", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.0, "smalltalk": 0.0}, "trace": {"path": "smalltalk"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:57560 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSNDQyMzA2RjJCMERGMDdCNDVEAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:48430 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSNDQyMzA2RjJCMERGMDdCNDVEAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:48438 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSNDQyMzA2RjJCMERGMDdCNDVEAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:48440 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "wht products do u sell", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "qdrant_search_failed", "error": "'AsyncQdrantClient' object has no attribute 'search'", "level": "ERROR", "logger": "qdrant"}
api-1  | {"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "c3ffc9e4-2c55-4674-abdc-7cf7e8836f92", "reason": "low_confidence", "detail": "wht products do u sell", "customer_wa_id": "917845965287"}, "level": "INFO", "logger": "events"}     
api-1  | {"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "low_confidence", "conversation": "c3ffc9e4-2c55-4674-abdc-7cf7e8836f92", "level": "INFO", "logger": "escalation"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.35, "fast_path": 14.76}, "trace": {"router_skipped": "price_stock_pattern", "intent": "catalog_qa", "confidence": 0.9, "degraded": false, "advisory": false, "fts_faq_rank": 0.0, "fts_products": 0, "semantic_chunks": 0, "path": "no_grounding"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:43408 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSREUyRTE4QzJCQjMxOThDNTQ4AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:43414 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSREUyRTE4QzJCQjMxOThDNTQ4AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:43422 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSREUyRTE4QzJCQjMxOThDNTQ4AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:43430 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "how much is argan oil", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "qdrant_search_failed", "error": "'AsyncQdrantClient' object has no attribute 'search'", "level": "ERROR", "logger": "qdrant"}
api-1  | {"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "c3ffc9e4-2c55-4674-abdc-7cf7e8836f92", "reason": "low_confidence", "detail": "how much is argan oil", "customer_wa_id": "917845965287"}, "level": "INFO", "logger": "events"}      
api-1  | {"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "low_confidence", "conversation": "c3ffc9e4-2c55-4674-abdc-7cf7e8836f92", "level": "INFO", "logger": "escalation"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.09, "guardrails": 0.01, "smalltalk": 0.02, "cache_lookup": 0.76, "fast_path": 1.18}, "trace": {"router_skipped": "price_stock_pattern", "intent": "catalog_qa", "confidence": 0.9, "degraded": false, "advisory": false, "fts_faq_rank": 0.0, "fts_products": 0, "semantic_chunks": 0, "path": "no_grounding"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51174 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSOTBFMjY1NTNFMjREMUZBRkY1AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51184 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSOTBFMjY1NTNFMjREMUZBRkY1AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51200 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSOTBFMjY1NTNFMjREMUZBRkY1AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51210 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "do u have shampoo for dandruff", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"message": "AFC is enabled with max remote calls: 10.", "level": "INFO", "logger": "google_genai.models"}
api-1  | {"message": "AFC is enabled with max remote calls: 10.", "level": "INFO", "logger": "google_genai.models"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.04, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.36, "fast_path": 0.01, "router": 1024.75}, "trace": {"fast_path_skipped": "advisory", "intent": "consultation", "confidence": 0.95, "degraded": false, "consult_concern_hits": 1, "path": "consult_recommend"}, "llm_calls": 2, "input_tokens": 710, "output_tokens": 143, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:42890 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSNjA0M0Y5RTM2MTJENjgzNzgyAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:42892 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSNjA0M0Y5RTM2MTJENjgzNzgyAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:42906 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSNjA0M0Y5RTM2MTJENjgzNzgyAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:42918 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "is ur shampoo sulfate free", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"message": "AFC is enabled with max remote calls: 10.", "level": "INFO", "logger": "google_genai.models"}
api-1  | {"event": "qdrant_search_failed", "error": "'AsyncQdrantClient' object has no attribute 'search'", "level": "ERROR", "logger": "qdrant"}
api-1  | {"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "c3ffc9e4-2c55-4674-abdc-7cf7e8836f92", "reason": "low_confidence", "detail": "is ur shampoo sulfate free", "customer_wa_id": "917845965287"}, "level": "INFO", "logger": "events"} 
api-1  | {"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "low_confidence", "conversation": "c3ffc9e4-2c55-4674-abdc-7cf7e8836f92", "level": "INFO", "logger": "escalation"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.04, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.33, "fast_path": 0.81, "router": 1012.42}, "trace": {"intent": "catalog_qa", "confidence": 0.95, "degraded": false, "advisory": false, "fts_faq_rank": 0.0, "fts_products": 0, "semantic_chunks": 0, "path": "no_grounding"}, "llm_calls": 1, "input_tokens": 445, "output_tokens": 74, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:50514 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQUJGQzlFODc5Qjk2MkYxMERCAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:38886 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQUJGQzlFODc5Qjk2MkYxMERCAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:38896 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQUJGQzlFODc5Qjk2MkYxMERCAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:38906 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "how long does delivery take", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.05, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.33, "fast_path": 2.21}, "trace": {"fast_path_faq_rank": 0.2669, "path": "faq_fast_path_prerouter"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:60898 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSOTI2NzFBMzYzNzFDRUMwQzMyAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:60902 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSOTI2NzFBMzYzNzFDRUMwQzMyAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:60908 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSOTI2NzFBMzYzNzFDRUMwQzMyAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:60920 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "wht is your return policies", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.01, "smalltalk": 0.02, "cache_lookup": 0.29, "fast_path": 1.69}, "trace": {"fast_path_faq_rank": 0.1882, "path": "faq_fast_path_prerouter"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33204 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzQzRDc0M0M5NzY3MDEzMjlFAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33210 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzQzRDc0M0M5NzY3MDEzMjlFAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33226 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzQzRDc0M0M5NzY3MDEzMjlFAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33234 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "I want to order ur oil", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.16, "guardrails": 0.02, "smalltalk": 0.02, "cache_lookup": 0.91, "fast_path": 2.16}, "trace": {"router_skipped": "order_pattern", "intent": "order_capture", "confidence": 0.9, "degraded": false, "path": "order_ask_quantity"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33500 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzMyQUI4M0VBODA3MjA4NTYzAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33506 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzMyQUI4M0VBODA3MjA4NTYzAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33508 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzMyQUI4M0VBODA3MjA4NTYzAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:33520 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "2", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.31}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false, "path": "order_ask_name"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:49864 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSM0NGMjExQTM0OEJFQzE0RUI2AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:49876 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSM0NGMjExQTM0OEJFQzE0RUI2AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:49886 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSM0NGMjExQTM0OEJFQzE0RUI2AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:49898 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "raveen", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.02, "guardrails": 0.0, "smalltalk": 0.01, "cache_lookup": 0.31}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false, "path": "order_ask_address"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:49902 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzRCMjY2MURCRTRDOTBCQTdCAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:49912 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzRCMjY2MURCRTRDOTBCQTdCAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:42332 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMzRCMjY2MURCRTRDOTBCQTdCAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:42336 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "no 2 tamilan nagar kavangarai", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.36}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false, "path": "order_ask_pincode"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:44270 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQzU0MUI0NTFGOEJGQ0MxOEQxAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:44272 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQzU0MUI0NTFGOEJGQ0MxOEQxAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:44278 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQzU0MUI0NTFGOEJGQ0MxOEQxAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:44288 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "600066", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.05, "guardrails": 0.0, "smalltalk": 0.01, "cache_lookup": 0.29}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false, "path": "order_ask_payment_method"}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:44304 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQjYyMDJGREZFNDdBNTJDMDY1AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:39108 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQjYyMDJGREZFNDdBNTJDMDY1AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:39120 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQjYyMDJGREZFNDdBNTJDMDY1AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:39132 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "cod", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.38}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}    
api-1  | INFO:     172.18.0.6:39148 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSODBGRTM3QjM5RTg4QzdGQzM3AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:39152 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSODBGRTM3QjM5RTg4QzdGQzM3AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:39156 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSODBGRTM3QjM5RTg4QzdGQzM3AA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:39158 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "yes", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.0, "smalltalk": 0.01, "cache_lookup": 0.31}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}     
api-1  | INFO:     172.18.0.6:34754 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMEI3QjA2QzcxRERFQTlFNUVBAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:34756 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMEI3QjA2QzcxRERFQTlFNUVBAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:34758 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSMEI3QjA2QzcxRERFQTlFNUVBAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:34764 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "domain_event", "name": "message.received", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "customer_wa_id": "917845965287", "text": "get outtt", "type": "text"}, "level": "INFO", "logger": "events"}
api-1  | {"event": "message_handled", "tenant": "glow-roots", "wa_id": "917845965287", "plan": "pro", "steps_ms": {"normalize": 0.03, "guardrails": 0.01, "smalltalk": 0.01, "cache_lookup": 0.33}, "trace": {"router_skipped": "mid_flow_slot_answer", "intent": "order_capture", "confidence": 1.0, "degraded": false}, "llm_calls": 0, "input_tokens": 0, "output_tokens": 0, "level": "INFO", "logger": "webhook"}    
api-1  | INFO:     172.18.0.6:51618 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "sent", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQzU5REM0OTIyMDNGQTBGQkMwAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51628 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "delivered", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQzU5REM0OTIyMDNGQTBGQkMwAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51642 - "POST /webhook HTTP/1.1" 200 OK
api-1  | {"event": "message_status", "status": "read", "wamid": "wamid.HBgMOTE3ODQ1OTY1Mjg3FQIAERgSQzU5REM0OTIyMDNGQTBGQkMwAA==", "level": "INFO", "logger": "webhook"}
api-1  | INFO:     172.18.0.6:51646 - "POST /webhook HTTP/1.1" 200 OK


[16:30, 30/07/2026] Raveen: hi
[16:30, 30/07/2026] +1 (555) 199-6360: Hi! Welcome to Glow Roots 🌿 How can I help you today?
[16:30, 30/07/2026] Raveen: wht products do u sell
[16:31, 30/07/2026] +1 (555) 199-6360: Let me check that with our team and get back to you shortly.
[16:31, 30/07/2026] Raveen: how much is argan oil
[16:31, 30/07/2026] +1 (555) 199-6360: Let me check that with our team and get back to you shortly.
[16:31, 30/07/2026] Raveen: do u have shampoo for dandruff
[16:31, 30/07/2026] +1 (555) 199-6360: To address your dandruff concerns, I recommend the Tea Tree Clarifying Shampoo. It is formulated with tea tree and salicylic acid to help cleanse the scalp and manage flaking. Since your hair is dry, you may want to follow up with a hydrating conditioner. 

Would you like to order this for INR 499?
[16:31, 30/07/2026] Raveen: is ur shampoo sulfate free
[16:31, 30/07/2026] +1 (555) 199-6360: Let me check that with our team and get back to you shortly.
[16:32, 30/07/2026] Raveen: how long does delivery take
[16:32, 30/07/2026] +1 (555) 199-6360: Metro cities usually get it in 2-3 working days, and the rest of India in 4-6 working days.

Would you like to place an order?
[16:32, 30/07/2026] Raveen: wht is your return policies
[16:32, 30/07/2026] +1 (555) 199-6360: Unopened products can be returned within 7 days of delivery. Opened bottles cannot be returned for hygiene reasons.

Would you like to place an order?
[16:32, 30/07/2026] Raveen: I want to order ur oil
[16:32, 30/07/2026] +1 (555) 199-6360: How many would you like?
[16:32, 30/07/2026] Raveen: 2
[16:32, 30/07/2026] +1 (555) 199-6360: What name should I put on the order?
[16:32, 30/07/2026] Raveen: raveen
[16:32, 30/07/2026] +1 (555) 199-6360: Please share your full delivery address.
[16:32, 30/07/2026] Raveen: no 2 tamilan nagar kavangarai
[16:32, 30/07/2026] +1 (555) 199-6360: And your pincode?
[16:33, 30/07/2026] Raveen: 600066
[16:33, 30/07/2026] +1 (555) 199-6360: Would you like to pay online (UPI/card) or cash on delivery?
[16:33, 30/07/2026] Raveen: cod
[16:33, 30/07/2026] +1 (555) 199-6360: Here's your order:

2 x Argan Repair Hair Oil
Total: INR 898
Delivery to 600066 by Sun, 02 Aug
Payment: Cash on delivery

Shall I confirm it?
[16:33, 30/07/2026] Raveen: yes
[16:33, 30/07/2026] +1 (555) 199-6360: Here's your order:

2 x Argan Repair Hair Oil
Total: INR 898
Delivery to 600066 by Sun, 02 Aug
Payment: Cash on delivery

Shall I confirm it?
[16:33, 30/07/2026] Raveen: get outtt
[16:33, 30/07/2026] +1 (555) 199-6360: Here's your order:

2 x Argan Repair Hair Oil
Total: INR 898
Delivery to 600066 by Sun, 02 Aug
Payment: Cash on delivery

Shall I confirm it?

wht is the reason for failure, sld we switch to complete ai api, or just some tweeks so everything works best and production ready

also whts our next phase shall we start it
