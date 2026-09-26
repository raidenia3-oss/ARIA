/*
AURA SUBDOMAIN ENUMERATOR

Concurrent subdomain enumeration using wordlists.
Features:
- Fast parallel enumeration
- Multiple wordlists
- JSON output
- Filter by alive/DNS
*/
package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"os"
	"sync"
	"time"
)

type SubdomainResult struct {
	Subdomain string    `json:"subdomain"`
	IP        string    `json:"ip,omitempty"`
	Found     bool      `json:"found"`
	Timestamp time.Time `json:"timestamp"`
}

type Enumerator struct {
	domain    string
	wordlist  []string
	workers   int
	results   []SubdomainResult
	mu        sync.Mutex
}

func NewEnumerator(domain string, workers int) *Enumerator {
	return &Enumerator{
		domain:   domain,
		workers:  workers,
		results:  make([]SubdomainResult, 0),
	}
}

func (e *Enumerator) LoadWordlist(filename string) error {
	file, err := os.Open(filename)
	if err != nil {
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		word := scanner.Text()
		if word != "" {
			e.wordlist = append(e.wordlist, word)
		}
	}

	return scanner.Err()
}

func (e *Enumerator) ResolveSubdomain(subdomain string) (string, bool) {
	ips, err := net.LookupIP(subdomain)
	if err != nil {
		return "", false
	}

	if len(ips) > 0 {
		return ips[0].String(), true
	}
	return "", false
}

func (e *Enumerator) EnumerateWorker(subdomainChan <-chan string, wg *sync.WaitGroup) {
	defer wg.Done()

	for subdomain := range subdomainChan {
		ip, found := e.ResolveSubdomain(subdomain)

		if found {
			result := SubdomainResult{
				Subdomain: subdomain,
				IP:        ip,
				Found:     true,
				Timestamp: time.Now(),
			}

			e.mu.Lock()
			e.results = append(e.results, result)
			e.mu.Unlock()

			fmt.Printf("[+] %s -> %s\n", subdomain, ip)
		}
	}
}

func (e *Enumerator) Enumerate() []SubdomainResult {
	subdomainChan := make(chan string, e.workers*2)
	var wg sync.WaitGroup

	// Launch workers
	for i := 0; i < e.workers; i++ {
		wg.Add(1)
		go e.EnumerateWorker(subdomainChan, &wg)
	}

	// Send subdomains
	go func() {
		for _, word := range e.wordlist {
			subdomain := fmt.Sprintf("%s.%s", word, e.domain)
			subdomainChan <- subdomain
		}
		close(subdomainChan)
	}()

	wg.Wait()

	return e.results
}

func main() {
	domain := flag.String("d", "", "Target domain")
	wordlist := flag.String("w", "wordlist.txt", "Wordlist file")
	workers := flag.Int("j", 10, "Number of workers")
	output := flag.String("o", "text", "Output format (text/json)")

	flag.Parse()

	if *domain == "" {
		fmt.Println("Error: domain required (-d)")
		flag.PrintDefaults()
		os.Exit(1)
	}

	fmt.Printf("[*] Loading wordlist from %s...\n", *wordlist)

	enumerator := NewEnumerator(*domain, *workers)
	err := enumerator.LoadWordlist(*wordlist)
	if err != nil {
		fmt.Printf("Error loading wordlist: %v\n", err)
		os.Exit(1)
	}

	fmt.Printf("[*] Loaded %d words\n", len(enumerator.wordlist))
	fmt.Printf("[*] Starting enumeration with %d workers...\n", *workers)

	start := time.Now()
	results := enumerator.Enumerate()
	duration := time.Since(start).Seconds()

	fmt.Printf("\n[*] Enumeration completed in %.2f seconds\n", duration)
	fmt.Printf("[*] Found %d subdomains\n", len(results))

	if *output == "json" {
		data, _ := json.MarshalIndent(results, "", "  ")
		fmt.Println(string(data))
	} else {
		for _, result := range results {
			fmt.Printf("%s -> %s\n", result.Subdomain, result.IP)
		}
	}
}
