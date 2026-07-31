PS D:\Projects\agent\whatsapp-ai-employee> docker compose exec api python -m scripts.eval_harness --delay 13 --verbose

model=gemini-3.1-flash-lite  router=gemini-3.1-flash-lite
plan=pro  fts_threshold=0.05
cases=27

PASS  greeting                        free      1ms
      Hi! Welcome to Glow Roots 🌿 How can I help you today?
PASS  thanks                          free      0ms
      Happy to help! Anything else you would like to know?
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"argan oil\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  price_known_product            1 llm   2817ms
      - intent=agent expected=catalog_qa
      reply: Hi Eval! Our Argan Repair Hair Oil comes in two sizes: 100ml for INR 449 and 200ml for INR 799.

Which size would you like to go for?
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"argan oil\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  price_larger_size              1 llm   2215ms
      - intent=agent expected=catalog_qa
      reply: Hi Eval! The 200ml Argan Repair Hair Oil is priced at INR 799. Would you like to go ahead and order it?
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"delivery charges\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  delivery_charges               1 llm   2408ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Hi Eval! Delivery is free on orders above INR 599, and INR 49 for orders below that.  

Are you looking for anything specific today?
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"shipping charges\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  delivery_charges_paraphrase    1 llm   2011ms
      - intent=agent expected=catalog_qa
      reply: Hi Eval! Delivery is free on orders over INR 599, otherwise it's just INR 49. Are you looking for anything in particular today?
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"delivery times\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  delivery_time                  1 llm   1972ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Hi Eval! Delivery usually takes 2-3 working days for metro cities and 4-6 working days for the rest of India. Are you looking for anything in particular today?
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"is cash on delivery available\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  cod_available                  1 llm   2264ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Yes, we offer cash on delivery for orders up to INR 2000! Are you looking for anything specific today, Eval?
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"return policy\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  return_policy                  1 llm   2058ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Hi Eval! Unopened products can be returned within 7 days of delivery, though opened bottles cannot be returned for hygiene reasons. Are you looking for somethin
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"are your products vegan\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  vegan                          1 llm   2366ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Hi Eval! Yes, all our products are 100% vegan and cruelty-free. Are you looking for something specific for your hair or skin today?
FAIL  sulphate_free                  1 llm   1125ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Hi Eval! Yes, many of our products are sulphate-free. Are you looking for a specific type of product, like a shampoo or a hair mask?
{"event": "tool_call", "tool": "get_shop_info", "args": "{\"question\": \"working hours\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  working_hours                  1 llm   1772ms
      - intent=agent expected=catalog_qa
      - cost 1 llm call(s), expected free
      reply: Hi Eval! We reply to messages between 10am and 7pm, Monday to Saturday. Are you looking for anything in particular today?
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"tea tree shampoo\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  stock_check                    1 llm   2322ms
      - intent=agent expected=catalog_qa
      reply: Hi Eval! Yes, we have the Tea Tree Clarifying Shampoo in stock for INR 499 (200 ml). It's formulated for oily scalps and flaking.

Would you like to go ahead an
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"silk finish serum\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  out_of_stock_item              1 llm   2861ms
      - intent=agent expected=catalog_qa
      reply: Hi Eval! The Silk Finish Hair Serum is priced at INR 399 for 50ml, but it is currently out of stock.

Would you like me to notify you when it's back, or are you
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"shampoo for dandruff\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  advisory_dandruff              1 llm   2595ms
      - intent=agent expected=consultation
      reply: Hi Eval! For dandruff, I recommend our Tea Tree Clarifying Shampoo, which is formulated with tea tree and salicylic acid to help with flaking and oily scalps.


FAIL  advisory_open_ended            1 llm   3655ms
      - intent=agent expected=consultation
      reply: Hi Eval! I'm sorry to hear your hair is feeling fragile. To help me recommend the best products for you, could you tell me if your hair is naturally dry or if i
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"tea tree shampoo\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  order_intent                   1 llm   2427ms
      - intent=agent expected=order_capture
      - cost 1 llm call(s), expected free
      reply: Hi Eval! I'd be happy to help you with that. We have the Tea Tree Clarifying Shampoo (200ml) for INR 499, which is formulated for oily scalps and flaking.

Woul
{"event": "tool_call", "tool": "get_order_status", "args": "{}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  order_status                   1 llm   2116ms
      - intent=agent expected=order_status
      - cost 1 llm call(s), expected free
      reply: Hi Eval! I'm sorry, I couldn't find any orders linked to your number. Would you like me to help you place a new order instead?
{"event": "tool_call", "tool": "get_order_status", "args": "{}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  order_status_paraphrase        1 llm   3888ms
      - intent=agent expected=order_status
      - cost 1 llm call(s), expected free
      reply: Hi Eval! I've checked our system, but I couldn't find any active orders linked to your account. Would you like me to help you place a new order today?
{"event": "tool_call", "tool": "search_catalog", "args": "{\"query\": \"ROSE-SHM-200\"}", "ok": true, "level": "INFO", "logger": "agent.loop"}
FAIL  deep_link_sku                  1 llm   2613ms
      - intent=agent expected=order_capture
      - cost 1 llm call(s), expected free
      reply: Hi Eval! The Rosemary Strengthening Shampoo (200ml) is a great choice for thinning and weak hair. It's priced at INR 549.

Would you like to go ahead and order
{"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "d19afdb1-7ee4-4a98-bd01-54ca50d36702", "reason": "human_request", "detail": "i want to talk to a human", "customer_wa_id": "919999900099"}, "level": "INFO", "logger": "events"}
{"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "human_request", "conversation": "d19afdb1-7ee4-4a98-bd01-54ca50d36702", "level": "INFO", "logger": "escalation"}
PASS  human_request                   free     23ms
      Sure — I'm connecting you to our team. Someone will reply here shortly.
{"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "6cfa8527-a2d1-4221-b84b-457a3a08e80e", "reason": "adverse_reaction", "detail": "matched 'burning' in: my scalp is burning after using the oil", "customer_wa_id": "919999900099"}, "level": "INFO", "logger": "events"}
{"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "adverse_reaction", "conversation": "6cfa8527-a2d1-4221-b84b-457a3a08e80e", "level": "INFO", "logger": "escalation"}
PASS  adverse_reaction                free      5ms
      Thank you for telling us, and I'm sorry you're experiencing this. Please stop using the product for now. I'm alerting our team right away and someone will conta
{"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "7d5dc7fa-6940-4ca1-9ce8-420700f20443", "reason": "medical", "detail": "matched 'alopecia' in: will this help with alopecia", "customer_wa_id": "919999900099"}, "level": "INFO", "logger": "events"}
{"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "medical", "conversation": "7d5dc7fa-6940-4ca1-9ce8-420700f20443", "level": "INFO", "logger": "escalation"}
PASS  medical_question                free      6ms
      That's a medical question, and I'm not able to advise on it. I've passed this to our team, and we'd recommend speaking to a doctor or dermatologist for anything
{"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "5c0c43a0-b04a-40b1-a87f-f69fda3fd691", "reason": "medical", "detail": "matched 'pregnant' in: is it safe while pregnant", "customer_wa_id": "919999900099"}, "level": "INFO", "logger": "events"}
{"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "medical", "conversation": "5c0c43a0-b04a-40b1-a87f-f69fda3fd691", "level": "INFO", "logger": "escalation"}
PASS  pregnancy_safety                free      4ms
      That's a medical question, and I'm not able to advise on it. I've passed this to our team, and we'd recommend speaking to a doctor or dermatologist for anything
{"event": "domain_event", "name": "escalation.raised", "payload": {"tenant_id": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "conversation_id": "d9f9b4b4-6d29-49d5-8b3b-56f89a62055b", "reason": "complaint", "detail": "matched 'scam' in: i still not received my order this is a scam", "customer_wa_id": "919999900099"}, "level": "INFO", "logger": "events"}
{"event": "escalation_raised", "tenant": "6bf6363c-74c7-4c38-b2f1-a1f8733ecb99", "reason": "complaint", "conversation": "d9f9b4b4-6d29-49d5-8b3b-56f89a62055b", "level": "INFO", "logger": "escalation"}
PASS  complaint                       free      6ms
      I'm sorry about this. I've escalated it to our team and someone will get back to you here shortly.
PASS  gibberish                       free      0ms
      Let me check that with our team and get back to you shortly.
PASS  emoji_only                      free      0ms
      Let me check that with our team and get back to you shortly.

==============================================================
accuracy        9/27  (33%)
free path       9/27  (33% cost nothing)
llm calls       18
tokens          47184 in / 1013 out
avg latency     1612 ms

cost/message    $0.000493   -> $1.48/month at 300 conversations

18 failing case(s):
  price_known_product: intent=agent expected=catalog_qa
  price_larger_size: intent=agent expected=catalog_qa
  delivery_charges: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  delivery_charges_paraphrase: intent=agent expected=catalog_qa
  delivery_time: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  cod_available: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  return_policy: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  vegan: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  sulphate_free: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  working_hours: intent=agent expected=catalog_qa; cost 1 llm call(s), expected free
  stock_check: intent=agent expected=catalog_qa
  out_of_stock_item: intent=agent expected=catalog_qa
  advisory_dandruff: intent=agent expected=consultation
  advisory_open_ended: intent=agent expected=consultation
  order_intent: intent=agent expected=order_capture; cost 1 llm call(s), expected free
  order_status: intent=agent expected=order_status; cost 1 llm call(s), expected free
  order_status_paraphrase: intent=agent expected=order_status; cost 1 llm call(s), expected free   
  deep_link_sku: intent=agent expected=order_capture; cost 1 llm call(s), expected free

Tip: 'cost N llm calls, expected free' usually means FTS_FAST_PATH_RANK is too high — run scripts.tune_retrieval.
==============================================================
PS D:\Projects\agent\whatsapp-ai-employee> 


r we making progess r not, i want to move forward with each step not stuck in a loop

abt our hypothesis to fix with this and agent works accordingly, so my new doubt is instead of creatng a automation per client, can we build multiple templates, like 5-10, and even with 1000 different client and 1000 differenct products, they will somehow fall under one category for our template. think and say which is best

whts the next step