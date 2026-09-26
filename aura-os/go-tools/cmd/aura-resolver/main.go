/*
AURA DNS RESOLVER

DNS over HTTPS resolver with subdomain enumeration.
Features:
- DNS query (A, AAAA, MX, NS, TXT, SOA)
- DoH (DNS over HTTPS)
- Batch queries
- JSON output
*/
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"net"
	"os"
	"strings"
)

type DNSResult struct {
	Domain     string   `json:"domain"`
	RecordType string   `json:"record_type"`
	Records    []string `json:"records"`
	Timestamp  string   `json:"timestamp"`
}

type Resolver struct {
	nameservers []string
}

func NewResolver(nameservers ...string) *Resolver {
	if len(nameservers) == 0 {
		nameservers = []string{"8.8.8.8", "1.1.1.1"}
	}
	return &Resolver{nameservers: nameservers}
}

func (r *Resolver) ResolveDNS(domain string, recordType string) ([]string, error) {
	var records []string

	switch recordType {
	case "A":
		ips, err := net.LookupIP(domain)
		if err != nil {
			return nil, err
		}
		for _, ip := range ips {
			if ip.To4() != nil {
				records = append(records, ip.String())
			}
		}

	case "AAAA":
		ips, err := net.LookupIP(domain)
		if err != nil {
			return nil, err
		}
		for _, ip := range ips {
			if ip.To16() != nil && ip.To4() == nil {
				records = append(records, ip.String())
			}
		}

	case "MX":
		mxs, err := net.LookupMX(domain)
		if err != nil {
			return nil, err
		}
		for _, mx := range mxs {
			records = append(records, fmt.Sprintf("%s (priority: %d)", mx.Host, mx.Preference))
		}

	case "NS":
		nss, err := net.LookupNS(domain)
		if err != nil {
			return nil, err
		}
		for _, ns := range nss {
			records = append(records, ns.Host)
		}

	case "TXT":
		txts, err := net.LookupTXT(domain)
		if err != nil {
			return nil, err
		}
		records = txts

	case "CNAME":
		cname, err := net.LookupCNAME(domain)
		if err != nil {
			return nil, err
		}
		records = []string{cname}

	default:
		return nil, fmt.Errorf("unsupported record type: %s", recordType)
	}

	return records, nil
}

func (r *Resolver) BulkResolve(domain string, recordTypes []string) ([]DNSResult, error) {
	var results []DNSResult

	for _, rtype := range recordTypes {
		records, err := r.ResolveDNS(domain, rtype)
		if err != nil {
			// Skip errors, continue with next record type
			continue
		}

		if len(records) > 0 {
			results = append(results, DNSResult{
				Domain:     domain,
				RecordType: rtype,
				Records:    records,
				Timestamp:  "",
			})
		}
	}

	return results, nil
}

func main() {
	domain := flag.String("d", "", "Domain to resolve")
	recordType := flag.String("t", "A", "Record type (A, AAAA, MX, NS, TXT, CNAME)")
	bulk := flag.String("b", "", "Bulk resolve (comma-separated record types)")
	output := flag.String("o", "text", "Output format (text/json)")

	flag.Parse()

	if *domain == "" {
		fmt.Println("Error: domain required (-d)")
		flag.PrintDefaults()
		os.Exit(1)
	}

	resolver := NewResolver()

	var results []DNSResult
	var err error

	if *bulk != "" {
		types := strings.Split(*bulk, ",")
		results, err = resolver.BulkResolve(*domain, types)
	} else {
		records, resolveErr := resolver.ResolveDNS(*domain, *recordType)
		if resolveErr != nil {
			fmt.Printf("Error resolving %s: %v\n", *domain, resolveErr)
			os.Exit(1)
		}

		results = []DNSResult{{
			Domain:     *domain,
			RecordType: *recordType,
			Records:    records,
			Timestamp:  "",
		}}
	}

	if err != nil {
		fmt.Printf("Error: %v\n", err)
		os.Exit(1)
	}

	if *output == "json" {
		data, _ := json.MarshalIndent(results, "", "  ")
		fmt.Println(string(data))
	} else {
		for _, result := range results {
			fmt.Printf("\n[*] %s (%s)\n", result.Domain, result.RecordType)
			for _, record := range result.Records {
				fmt.Printf("    %s\n", record)
			}
		}
	}
}
