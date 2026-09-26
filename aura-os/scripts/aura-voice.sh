#!/bin/sh
# AURA Personal Assistant CON VOZ

clear

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║     🤖 AURA Personal Assistant v1.0 (WITH VOICE)             ║"
echo "║                                                                ║"
echo "║         Backend: http://localhost:8000                        ║"
echo "║         Voice: espeak (English)                               ║"
echo "║         Type 'exit' to quit                                   ║"
echo "║                                                                ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

API_URL="http://localhost:8000/api/chat"

while true; do
    echo -n "You: "
    read -r user_input
    
    if [ "$user_input" = "exit" ]; then
        echo ""
        echo "AURA: Goodbye! See you next time."
        espeak "Goodbye! See you next time." 2>/dev/null
        break
    fi
    
    if [ -z "$user_input" ]; then
        continue
    fi
    
    echo "AURA: Thinking..."
    
    response=$(curl -s -X POST "$API_URL" \
      -H "Content-Type: application/json" \
      -d "{\"message\": \"$user_input\"}" 2>/dev/null)
    
    if echo "$response" | grep -q '"response"'; then
        answer=$(echo "$response" | jq -r '.response' 2>/dev/null)
        echo "AURA: $answer"
        
        echo "$answer" | espeak -s 150 -p 50 2>/dev/null
    else
        echo "AURA: Error connecting"
        espeak "Error connecting" 2>/dev/null
    fi
    
    echo ""
done
