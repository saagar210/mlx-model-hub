#!/bin/bash
# Batch 6 - Final 150 topics mega batch
# Usage: ./scripts/ollama_generate_batch6.sh

set -e

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"
PROJECT_DIR="/Users/d/claude-code/personal/knowledge-activation-system"

echo "🚀 Ollama Batch 6 - MEGA BATCH (150 topics)"
echo "==========================================="

if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &
    sleep 5
fi

ollama pull qwen2.5:7b > /dev/null 2>&1

echo "📚 Generating 150 guides..."
echo ""

count=0
total=150

declare -a topics=(
    # Networking & Protocols
    "HTTP/2 Protocol Guide 2026|http2,protocol,networking,web"
    "HTTP/3 and QUIC 2026|http3,quic,protocol,performance"
    "DNS Deep Dive 2026|dns,networking,internet,resolution"
    "TCP/IP Fundamentals 2026|tcp,ip,networking,protocol"
    "TLS/SSL Certificates 2026|tls,ssl,security,encryption"
    "WebSockets Protocol 2026|websockets,protocol,realtime,networking"
    "gRPC Protocol Deep Dive 2026|grpc,protocol,rpc,performance"
    "MQTT IoT Protocol 2026|mqtt,iot,protocol,messaging"
    "AMQP Messaging Protocol 2026|amqp,protocol,messaging,rabbitmq"
    "SMTP Email Protocol 2026|smtp,email,protocol,mail"
    "IMAP Email Protocol 2026|imap,email,protocol,mail"
    "FTP and SFTP Guide 2026|ftp,sftp,file-transfer,protocol"
    "SSH Secure Shell 2026|ssh,secure,shell,remote"
    "VPN Protocols Comparison 2026|vpn,protocols,security,networking"
    "Load Balancing Algorithms 2026|load-balancing,algorithms,networking,performance"

    # Linux & System Administration
    "systemd Service Management 2026|systemd,linux,services,init"
    "Cron Job Scheduling 2026|cron,scheduling,automation,linux"
    "Bash Scripting Advanced 2026|bash,scripting,shell,automation"
    "awk Text Processing 2026|awk,text-processing,unix,scripting"
    "sed Stream Editor 2026|sed,text-processing,unix,scripting"
    "grep Pattern Matching 2026|grep,search,pattern,unix"
    "find File Search 2026|find,search,files,unix"
    "rsync File Sync 2026|rsync,sync,backup,files"
    "tar Archive Management 2026|tar,archive,compression,backup"
    "systemctl Service Control 2026|systemctl,systemd,services,linux"
    "journalctl Log Viewing 2026|journalctl,logs,systemd,debugging"
    "netstat Network Stats 2026|netstat,networking,monitoring,linux"
    "ss Socket Statistics 2026|ss,sockets,networking,linux"
    "htop Process Monitor 2026|htop,monitoring,processes,linux"
    "tmux Terminal Multiplexer 2026|tmux,terminal,multiplexer,productivity"

    # Web Servers & Proxies
    "Apache HTTP Server 2026|apache,http,server,web"
    "Caddy Web Server 2026|caddy,http,server,automatic-https"
    "HAProxy Load Balancer 2026|haproxy,load-balancer,proxy,performance"
    "Squid Proxy Server 2026|squid,proxy,cache,http"
    "Pound Reverse Proxy 2026|pound,reverse-proxy,load-balancer,http"

    # Configuration Management
    "Chef Configuration Management 2026|chef,configuration,infrastructure,automation"
    "Puppet Infrastructure Automation 2026|puppet,configuration,infrastructure,automation"
    "SaltStack Event-Driven 2026|saltstack,configuration,event-driven,automation"
    "Ansible Tower AWX 2026|ansible,tower,awx,automation"

    # Monitoring Solutions
    "Nagios Monitoring System 2026|nagios,monitoring,alerting,infrastructure"
    "Zabbix Monitoring Platform 2026|zabbix,monitoring,infrastructure,metrics"
    "Icinga Monitoring Tool 2026|icinga,monitoring,alerting,infrastructure"
    "Sensu Monitoring Framework 2026|sensu,monitoring,events,infrastructure"
    "Checkmk Monitoring Suite 2026|checkmk,monitoring,infrastructure,metrics"

    # Log Management
    "Fluentd Log Collector 2026|fluentd,logging,collector,aggregation"
    "Logstash Data Pipeline 2026|logstash,logging,pipeline,elk"
    "Graylog Log Management 2026|graylog,logging,management,analysis"
    "Loki Log Aggregation 2026|loki,logging,grafana,aggregation"
    "Vector Log Router 2026|vector,logging,routing,observability"

    # Service Discovery
    "Eureka Service Discovery 2026|eureka,service-discovery,netflix,microservices"
    "ZooKeeper Coordination 2026|zookeeper,coordination,distributed,apache"
    "etcd Distributed KV 2026|etcd,key-value,distributed,kubernetes"

    # API Management
    "Kong API Gateway 2026|kong,api-gateway,microservices,management"
    "Tyk API Gateway 2026|tyk,api-gateway,management,platform"
    "Apigee API Platform 2026|apigee,api,platform,google"
    "AWS API Gateway 2026|aws,api-gateway,serverless,management"
    "Express Gateway API 2026|express,gateway,api,nodejs"

    # Testing Frameworks
    "Mocha JavaScript Testing 2026|mocha,testing,javascript,unit"
    "Chai Assertion Library 2026|chai,assertions,testing,javascript"
    "Jasmine Testing Framework 2026|jasmine,testing,javascript,bdd"
    "Karma Test Runner 2026|karma,testing,runner,javascript"
    "Protractor E2E Testing 2026|protractor,e2e,testing,angular"
    "TestCafe E2E Testing 2026|testcafe,e2e,testing,javascript"
    "Puppeteer Headless Chrome 2026|puppeteer,headless,chrome,automation"
    "Nightwatch.js E2E Testing 2026|nightwatch,e2e,testing,selenium"
    "WebdriverIO Testing 2026|webdriverio,testing,selenium,automation"
    "Robot Framework Testing 2026|robot,framework,testing,automation"
    "Cucumber BDD Testing 2026|cucumber,bdd,testing,gherkin"
    "SpecFlow .NET BDD 2026|specflow,bdd,dotnet,testing"
    "Behave Python BDD 2026|behave,bdd,python,testing"
    "JUnit Java Testing 2026|junit,java,testing,unit"
    "TestNG Java Testing 2026|testng,java,testing,framework"
    "NUnit .NET Testing 2026|nunit,dotnet,testing,unit"
    "xUnit .NET Testing 2026|xunit,dotnet,testing,unit"
    "pytest Python Testing 2026|pytest,python,testing,framework"
    "unittest Python Testing 2026|unittest,python,testing,standard"
    "RSpec Ruby Testing 2026|rspec,ruby,testing,bdd"
    "Minitest Ruby Testing 2026|minitest,ruby,testing,unit"

    # Performance Testing
    "Apache JMeter Load Testing 2026|jmeter,load-testing,performance,apache"
    "Gatling Performance Testing 2026|gatling,performance,load-testing,scala"
    "Locust Load Testing 2026|locust,load-testing,python,distributed"
    "Artillery Load Testing 2026|artillery,load-testing,nodejs,performance"
    "Vegeta HTTP Load Testing 2026|vegeta,http,load-testing,go"

    # Code Coverage
    "Istanbul JavaScript Coverage 2026|istanbul,coverage,javascript,testing"
    "NYC Code Coverage 2026|nyc,coverage,javascript,testing"
    "Coverage.py Python Coverage 2026|coverage,python,testing,metrics"
    "JaCoCo Java Coverage 2026|jacoco,java,coverage,testing"
    "Cobertura Coverage Tool 2026|cobertura,coverage,java,testing"

    # Continuous Integration
    "TeamCity CI Server 2026|teamcity,ci,jetbrains,automation"
    "Bamboo CI Server 2026|bamboo,ci,atlassian,automation"
    "GoCD Continuous Delivery 2026|gocd,cd,pipeline,automation"
    "Concourse CI 2026|concourse,ci,pipeline,automation"
    "Buildkite CI Platform 2026|buildkite,ci,platform,automation"

    # Container Registry
    "Harbor Container Registry 2026|harbor,registry,containers,vmware"
    "Nexus Repository Manager 2026|nexus,repository,artifacts,sonatype"
    "Artifactory Repository 2026|artifactory,repository,jfrog,artifacts"
    "GitLab Container Registry 2026|gitlab,registry,containers,ci"
    "Amazon ECR Registry 2026|ecr,aws,registry,containers"

    # Infrastructure as Code
    "CloudFormation AWS IaC 2026|cloudformation,aws,iac,templates"
    "ARM Templates Azure 2026|arm,azure,templates,iac"
    "Bicep Azure IaC 2026|bicep,azure,iac,dsl"
    "CDK Cloud Development Kit 2026|cdk,aws,iac,typescript"
    "Crossplane Kubernetes IaC 2026|crossplane,kubernetes,iac,cloud-native"

    # Serverless Frameworks
    "Serverless Framework 2026|serverless,framework,lambda,deployment"
    "SAM Serverless Application Model 2026|sam,aws,serverless,deployment"
    "Chalice Python Serverless 2026|chalice,python,serverless,aws"
    "Zappa Python Serverless 2026|zappa,python,serverless,aws"
    "Up Serverless Deployment 2026|up,serverless,deployment,apex"

    # Message Brokers
    "ActiveMQ Message Broker 2026|activemq,messaging,jms,apache"
    "HiveMQ MQTT Broker 2026|hivemq,mqtt,broker,iot"
    "Mosquitto MQTT Broker 2026|mosquitto,mqtt,broker,lightweight"
    "Redis Pub/Sub Messaging 2026|redis,pubsub,messaging,realtime"
    "ZeroMQ Messaging Library 2026|zeromq,messaging,library,distributed"

    # Data Serialization
    "MessagePack Serialization 2026|messagepack,serialization,binary,data"
    "Avro Data Serialization 2026|avro,serialization,schema,hadoop"
    "Thrift Binary Protocol 2026|thrift,binary,serialization,rpc"
    "Cap'n Proto Serialization 2026|capnproto,serialization,rpc,performance"
    "FlatBuffers Serialization 2026|flatbuffers,serialization,google,performance"

    # API Documentation
    "Stoplight API Design 2026|stoplight,api,design,openapi"
    "Postman Documentation 2026|postman,documentation,api,collaboration"
    "Insomnia Designer 2026|insomnia,designer,api,rest"
    "API Blueprint Format 2026|api-blueprint,documentation,markdown,format"
    "RAML API Modeling 2026|raml,api,modeling,specification"

    # GraphQL Tools
    "Apollo Federation 2026|apollo,federation,graphql,microservices"
    "Hasura GraphQL Engine 2026|hasura,graphql,engine,postgresql"
    "Postgraphile GraphQL 2026|postgraphile,graphql,postgresql,api"
    "Prisma GraphQL 2026|prisma,graphql,orm,database"
    "GraphQL Yoga Server 2026|graphql-yoga,server,nodejs,graphql"

    # WebAssembly
    "WebAssembly WASM Basics 2026|webassembly,wasm,performance,web"
    "Emscripten C++ to WASM 2026|emscripten,cpp,wasm,compiler"
    "AssemblyScript WASM 2026|assemblyscript,typescript,wasm,compiler"
    "Blazor WebAssembly 2026|blazor,webassembly,dotnet,spa"
    "WASI WebAssembly System Interface 2026|wasi,webassembly,system,interface"

    # Edge Computing
    "Fastly Edge Computing 2026|fastly,edge,cdn,computing"
    "AWS CloudFront Edge 2026|cloudfront,aws,cdn,edge"
    "Akamai Edge Platform 2026|akamai,edge,cdn,platform"
    "Vercel Edge Functions 2026|vercel,edge,functions,serverless"
    "Netlify Edge Functions 2026|netlify,edge,functions,serverless"

    # Workflow Engines
    "Temporal Workflow Engine 2026|temporal,workflow,orchestration,microservices"
    "Cadence Workflow Platform 2026|cadence,workflow,orchestration,uber"
    "Argo Workflows 2026|argo,workflows,kubernetes,cicd"
    "n8n Workflow Automation 2026|n8n,workflow,automation,nocode"
    "Node-RED Flow Programming 2026|nodered,flow,iot,automation"
)

for topic_data in "${topics[@]}"; do
    count=$((count + 1))
    IFS='|' read -r topic tags <<< "$topic_data"
    
    echo "[$count/$total] $topic"
    
    prompt="Create a comprehensive technical guide about '$topic'. Include: clear sections, code examples, best practices, common patterns, performance tips, security considerations, and a summary. Markdown format. Detailed (40-80KB)."
    
    echo "  📝 Generating..."
    ollama run qwen2.5:7b "$prompt" 2>/dev/null > "/tmp/${topic}.md"
    
    if [ ! -s "/tmp/${topic}.md" ]; then
        echo "  ❌ Failed"
        continue
    fi
    
    cat > "$OBSIDIAN_DIR/${topic}.md" << EOF
---
type: reference
tags: [${tags}]
captured_at: '$(date +%Y-%m-%d)'
generated_by: ollama-qwen2.5-batch6
---

# ${topic}

$(cat "/tmp/${topic}.md")

---

## Sources

Generated using Ollama with Qwen2.5-7B model.
EOF
    
    echo "  ✅ Saved"
    rm "/tmp/${topic}.md"
    sleep 2
    echo ""
done

echo "======================================"
echo "📥 Ingesting into database..."
echo "======================================"

cd "$PROJECT_DIR"
source .venv/bin/activate
python cli.py ingest directory "$OBSIDIAN_DIR"

echo ""
echo "✅ MEGA BATCH 6 complete! Generated $count guides"
