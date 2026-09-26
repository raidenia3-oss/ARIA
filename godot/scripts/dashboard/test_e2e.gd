extends Node

class_name AuraE2ETest

var tests_passed := 0
var tests_failed := 0
var results := []

func _ready() -> void:
	pass

func run_all_tests() -> void:
	print("\n" + "=".repeat(60))
	print("AURA v3.0 - END-TO-END TESTING SUITE")
	print("=".repeat(60) + "\n")

	test_backend_health()
	test_brain_endpoints()
	test_routing_endpoints()
	test_treasury_endpoints()
	test_training_endpoints()
	test_rollercoin_endpoints()
	test_chat_endpoints()
	test_dashboard_panels_initialize()

	print("\n" + "=".repeat(60))
	print("TEST SUMMARY")
	print("=".repeat(60))
	print("Passed: %d" % tests_passed)
	print("Failed: %d" % tests_failed)
	if tests_failed == 0:
		print("\nALL TESTS PASSED - AURA v3.0 READY")
	else:
		print("\nSOME TESTS FAILED - REVIEW ABOVE")
	print("=".repeat(60) + "\n")

func _assert(condition: bool, message: String) -> void:
	if condition:
		tests_passed += 1
		results.append({"test": message, "status": "PASS"})
		print("[PASS] %s" % message)
	else:
		tests_failed += 1
		results.append({"test": message, "status": "FAIL"})
		print("[FAIL] %s" % message)

func _get_api_base() -> String:
	return "http://127.0.0.1:8000"

func _request_json(path: String, method: int = HTTPClient.METHOD_GET) -> Dictionary:
	var client := HTTPClient.new()
	var url := _get_api_base().rsplit("/", 1)[0] + path if path.begins_with("/") else "%s/%s" % [_get_api_base(), path]
	var err := client.connect_to_url(url)
	if err != OK:
		return {}
	err = client.request(method, path if path.begins_with("/") else "/" + path, [])
	if err != OK:
		return {}
	var start := Time.get_ticks_msec()
	while client.get_status() == HTTPClient.STATUS_REQUESTING or client.get_status() == HTTPClient.STATUS_BODY:
		client.poll()
		if Time.get_ticks_msec() - start > 5000:
			return {}
	var chunks := []
	while client.get_status() == HTTPClient.STATUS_BODY:
		var chunk := client.read_response_body_chunk()
		if chunk.is_empty():
			break
		chunks.append(chunk.get_string_from_utf8())
	var body := "".join(chunks)
	var data := JSON.parse_string(body)
	return data if data is Dictionary else {}

func test_backend_health() -> void:
	print("TEST 1: Backend Health")
	var data := _request_json("/health")
	_assert(not data.is_empty(), "Backend responded to /health")
	if not data.is_empty():
		_assert(data.get("status") in ["healthy", "ok"], "Backend status is healthy/ok")

func test_brain_endpoints() -> void:
	print("\nTEST 2: Brain Endpoints")
	var status := _request_json("/api/brain/status")
	_assert(not status.is_empty(), "Brain status responded")
	if not status.is_empty():
		_assert(status.has("state"), "Brain status contains state")
		_assert(status.has("registry"), "Brain status contains registry")

	var learn_payload := JSON.stringify({
		"device": "test",
		"role": "tester",
		"prompt": "e2e test",
		"response": "e2e response",
		"provider": "test"
	})
	var client := HTTPClient.new()
	var base := _get_api_base()
	var err := client.connect_to_url(base)
	if err == OK:
		err = client.request(HTTPClient.METHOD_POST, "/api/brain/learn", [], learn_payload)
		if err == OK:
			var start := Time.get_ticks_msec()
			while client.get_status() == HTTPClient.STATUS_REQUESTING or client.get_status() == HTTPClient.STATUS_BODY:
				client.poll()
				if Time.get_ticks_msec() - start > 5000:
					break
			var chunks := []
			while client.get_status() == HTTPClient.STATUS_BODY:
				var chunk := client.read_response_body_chunk()
				if chunk.is_empty():
					break
				chunks.append(chunk.get_string_from_utf8())
			var body := "".join(chunks)
			var data := JSON.parse_string(body)
			_assert(data is Dictionary and data.get("status") == "learned", "Brain learn endpoint works")

func test_routing_endpoints() -> void:
	print("\nTEST 3: Routing Endpoints")
	var status := _request_json("/api/brain/route/status")
	_assert(not status.is_empty(), "Routing status responded")
	if not status.is_empty():
		_assert(status.has("available_targets") or status.has("last_route"), "Routing status has expected fields")

	var history := _request_json("/api/brain/route/history?limit=1")
	_assert(not history.is_empty(), "Routing history responded")

func test_treasury_endpoints() -> void:
	print("\nTEST 4: Treasury Endpoints")
	var status := _request_json("/api/brain/treasury/status")
	_assert(not status.is_empty(), "Treasury status responded")
	if not status.is_empty():
		_assert(status.has("tier") or status.has("api_budget") or status.has("allocation"), "Treasury status has allocation data")

	var forecast := _request_json("/api/brain/treasury/forecast?days=1")
	_assert(not forecast.is_empty(), "Treasury forecast responded")

func test_training_endpoints() -> void:
	print("\nTEST 5: Training Endpoints")
	var status := _request_json("/api/brain/training/status")
	_assert(not status.is_empty(), "Training status responded")
	if not status.is_empty():
		_assert(status.has("status"), "Training status has status field")

	var history := _request_json("/api/brain/training/distillation-history?limit=1")
	_assert(not history.is_empty(), "Distillation history responded")

	var sync_resp := _request_json("/api/brain/training/sync?source=server")
	_assert(not sync_resp.is_empty(), "Training sync responded")

func test_rollercoin_endpoints() -> void:
	print("\nTEST 6: Rollercoin Endpoints")
	var status := _request_json("/api/rollercoin/status")
	_assert(not status.is_empty(), "Rollercoin status responded")
	if not status.is_empty():
		_assert(status.has("running") or status.has("daily_earnings") or status.has("goal"), "Rollercoin status has expected fields")

func test_chat_endpoints() -> void:
	print("\nTEST 7: Chat Endpoints")
	var client := HTTPClient.new()
	var base := _get_api_base()
	var err := client.connect_to_url(base)
	if err == OK:
		var payload := JSON.stringify({"prompt": "hola"})
		err = client.request(HTTPClient.METHOD_POST, "/api/chat", [], payload)
		if err == OK:
			var start := Time.get_ticks_msec()
			while client.get_status() == HTTPClient.STATUS_REQUESTING or client.get_status() == HTTPClient.STATUS_BODY:
				client.poll()
				if Time.get_ticks_msec() - start > 10000:
					break
			var chunks := []
			while client.get_status() == HTTPClient.STATUS_BODY:
				var chunk := client.read_response_body_chunk()
				if chunk.is_empty():
					break
				chunks.append(chunk.get_string_from_utf8())
			var body := "".join(chunks)
			var data := JSON.parse_string(body)
			_assert(data is Dictionary and not data.get("text", "").is_empty(), "Chat endpoint responds with text")

func test_dashboard_panels_initialize() -> void:
	print("\nTEST 8: Dashboard Panels Initialize")
	var dashboard := get_tree().get_first_node_in_group("dashboard") as Control
	if not dashboard:
		var candidates := get_tree().get_nodes_in_group("dashboard")
		if candidates.size() > 0:
			dashboard = candidates[0] as Control
	_assert(dashboard != null, "Dashboard node exists in scene")
	if dashboard:
		var has_panels := dashboard.get_child_count() > 0
		_assert(has_panels, "Dashboard has child panels")
		var any_panel := dashboard.find_child("PanelContainer", true, false) != null
		_assert(any_panel, "At least one panel container exists")
