-- load-test-chat.lua

wrk.method = "POST"
wrk.body = '{"message":"What is AURA OS?","skill_id":"chat"}'
wrk.headers["Content-Type"] = "application/json"

request = function()
  return wrk.format(nil, wrk.path)
end

response = function(status, headers, body)
  if status ~= 200 then
    io.stderr:write(string.format("Error %d\n", status))
  end
end
