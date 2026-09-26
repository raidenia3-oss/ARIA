$workflow = @{
    nodes = @(
        @{name="Trigger";type="n8n-nodes-base.cronTrigger";parameters=@{timeZone="America/Lima";interval=6;intervalUnit="hours"}},
        @{name="MyAnimeList";type="n8n-nodes-base.httpRequest";parameters=@{method="GET";url="https://myanimelist.net/rss.php?type=anime"}},
        @{name="Analyze";type="n8n-nodes-base.function";parameters=@{functionCode="return $input.all()"}},
        @{name="PostgreSQL";type="n8n-nodes-base.postgres";parameters=@{operation="insert";tableName="news_articles"}},
        @{name="FastAPI";type="n8n-nodes-base.httpRequest";parameters=@{method="POST";url="https://app-xxx.railway.app/api/news/analyze"}}
    )
    connections = @{
        Trigger = @("MyAnimeList")
        MyAnimeList = @("Analyze")
        Analyze = @("PostgreSQL")
        PostgreSQL = @("FastAPI")
    }
} | ConvertTo-Json -Depth 10

Set-Content "n8n/aura_news_workflow.json" -Value $workflow
Write-Host "✅ Workflow N8N regenerado correctamente"