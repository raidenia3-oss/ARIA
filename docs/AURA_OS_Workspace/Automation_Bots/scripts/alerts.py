from alerts import check_and_alert, send_daily_summary, send_whatsapp

@app.get("/alerts/check")
async def run_alerts():
    result = check_and_alert()
    return result

@app.get("/alerts/daily")
async def daily_summary():
    success = send_daily_summary()
    return {"sent": success}

@app.post("/alerts/custom")
async def custom_alert(request: Request):
    data = await request.json()
    message = data.get("message", "")
    if message:
        success = send_whatsapp(f"◈ AURA\n{message}")
        return {"sent": success}
    return {"sent": False}