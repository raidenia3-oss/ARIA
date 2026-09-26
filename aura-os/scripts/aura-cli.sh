#!/bin/sh
# AURA Personal Assistant CLI

clear

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                                                                ║"
echo "║          🤖 AURA Personal Assistant v1.0                     ║"
echo "║                                                                ║"
echo "║         Backend: http://localhost:8000                        ║"
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
        echo "✓ AURA saying goodbye..."
        echo "Goodbye! See you next time."
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
    else
        echo "AURA: ✗ Error connecting to backend"
    fi
    
    echo ""
done
