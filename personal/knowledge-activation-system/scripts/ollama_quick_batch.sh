#!/bin/bash
# Quick batch - 150 short topics to reach 1,000
# Usage: ./scripts/ollama_quick_batch.sh

set -e

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"
PROJECT_DIR="/Users/d/claude-code/personal/knowledge-activation-system"

echo "🚀 Quick Batch - 150 topics"
echo "==========================="

if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &
    sleep 5
fi

ollama pull qwen2.5:7b > /dev/null 2>&1

echo "📚 Generating..."
echo ""

count=0
total=150

declare -a topics=(
    # Protocols
    "HTTP2 Protocol|http2,protocol,web"
    "HTTP3 QUIC|http3,quic,protocol"
    "DNS Guide|dns,networking"
    "TCP IP|tcp,ip,networking"
    "TLS SSL|tls,ssl,security"
    "WebSockets|websockets,realtime"
    "gRPC Guide|grpc,rpc"
    "MQTT IoT|mqtt,iot"
    "AMQP Messaging|amqp,messaging"
    "SMTP Email|smtp,email"
    # Linux
    "systemd Guide|systemd,linux"
    "Cron Jobs|cron,scheduling"
    "Bash Advanced|bash,scripting"
    "awk Tutorial|awk,text"
    "sed Tutorial|sed,text"
    "grep Tutorial|grep,search"
    "find Command|find,files"
    "rsync Guide|rsync,backup"
    "tar Guide|tar,archive"
    "tmux Guide|tmux,terminal"
    # Web Servers
    "Apache Server|apache,http"
    "Caddy Server|caddy,https"
    "HAProxy Guide|haproxy,proxy"
    "Squid Proxy|squid,cache"
    # Config Management
    "Chef Guide|chef,config"
    "Puppet Guide|puppet,config"
    "SaltStack|saltstack,config"
    "Ansible Tower|ansible,tower"
    # Monitoring
    "Nagios Guide|nagios,monitoring"
    "Zabbix Guide|zabbix,monitoring"
    "Icinga Guide|icinga,monitoring"
    "Sensu Guide|sensu,monitoring"
    "Checkmk|checkmk,monitoring"
    # Logging
    "Fluentd Guide|fluentd,logging"
    "Logstash Guide|logstash,elk"
    "Graylog Guide|graylog,logging"
    "Loki Guide|loki,logging"
    "Vector Guide|vector,logging"
    # Service Discovery
    "Eureka Guide|eureka,discovery"
    "ZooKeeper|zookeeper,coordination"
    "etcd Guide|etcd,kv"
    # API Gateway
    "Kong Gateway|kong,api"
    "Tyk Gateway|tyk,api"
    "Apigee|apigee,api"
    "AWS Gateway|aws,api"
    "Express Gateway|express,api"
    # Testing JS
    "Mocha Testing|mocha,testing"
    "Chai Assertions|chai,testing"
    "Jasmine Testing|jasmine,bdd"
    "Karma Runner|karma,testing"
    "Protractor E2E|protractor,e2e"
    "TestCafe|testcafe,e2e"
    "Puppeteer|puppeteer,chrome"
    "Nightwatch|nightwatch,selenium"
    "WebdriverIO|webdriverio,selenium"
    # Testing General
    "Robot Framework|robot,testing"
    "Cucumber BDD|cucumber,bdd"
    "SpecFlow NET|specflow,bdd"
    "Behave Python|behave,bdd"
    "JUnit Java|junit,java"
    "TestNG Java|testng,java"
    "NUnit NET|nunit,dotnet"
    "xUnit NET|xunit,dotnet"
    "pytest Guide|pytest,python"
    "unittest Python|unittest,python"
    "RSpec Ruby|rspec,ruby"
    "Minitest Ruby|minitest,ruby"
    # Load Testing
    "JMeter Guide|jmeter,load"
    "Gatling Guide|gatling,load"
    "Locust Guide|locust,load"
    "Artillery Guide|artillery,load"
    "Vegeta HTTP|vegeta,load"
    # Coverage
    "Istanbul JS|istanbul,coverage"
    "NYC Coverage|nyc,coverage"
    "Coverage.py|coverage,python"
    "JaCoCo Java|jacoco,coverage"
    "Cobertura|cobertura,coverage"
    # CI Tools
    "TeamCity|teamcity,ci"
    "Bamboo CI|bamboo,ci"
    "GoCD Guide|gocd,cd"
    "Concourse CI|concourse,ci"
    "Buildkite|buildkite,ci"
    # Container Registry
    "Harbor Registry|harbor,registry"
    "Nexus Repository|nexus,repository"
    "Artifactory|artifactory,repository"
    "GitLab Registry|gitlab,registry"
    "Amazon ECR|ecr,aws"
    # IaC
    "CloudFormation|cloudformation,iac"
    "ARM Templates|arm,azure"
    "Bicep Azure|bicep,iac"
    "CDK Guide|cdk,aws"
    "Crossplane|crossplane,kubernetes"
    # Serverless
    "Serverless FW|serverless,lambda"
    "SAM AWS|sam,serverless"
    "Chalice Python|chalice,serverless"
    "Zappa Python|zappa,serverless"
    # Message Brokers
    "ActiveMQ|activemq,messaging"
    "HiveMQ MQTT|hivemq,mqtt"
    "Mosquitto MQTT|mosquitto,mqtt"
    "Redis PubSub|redis,pubsub"
    "ZeroMQ|zeromq,messaging"
    # Serialization
    "MessagePack|messagepack,serialization"
    "Avro Guide|avro,serialization"
    "Thrift Guide|thrift,serialization"
    "FlatBuffers|flatbuffers,serialization"
    # API Docs
    "Stoplight API|stoplight,api"
    "Postman Docs|postman,api"
    "Insomnia|insomnia,api"
    "API Blueprint|api-blueprint,docs"
    "RAML Guide|raml,api"
    # GraphQL
    "Apollo Federation|apollo,graphql"
    "Hasura Engine|hasura,graphql"
    "Postgraphile|postgraphile,graphql"
    "Prisma GraphQL|prisma,graphql"
    "GraphQL Yoga|graphql-yoga,graphql"
    # WebAssembly
    "WebAssembly Basics|webassembly,wasm"
    "Emscripten|emscripten,wasm"
    "AssemblyScript|assemblyscript,wasm"
    "Blazor WASM|blazor,wasm"
    "WASI Guide|wasi,wasm"
    # Edge Computing
    "Fastly Edge|fastly,edge"
    "CloudFront|cloudfront,cdn"
    "Akamai|akamai,cdn"
    "Vercel Edge|vercel,edge"
    "Netlify Edge|netlify,edge"
    # Workflows
    "Temporal|temporal,workflow"
    "Cadence|cadence,workflow"
    "Argo Workflows|argo,workflows"
    "n8n Automation|n8n,automation"
    "Node-RED|nodered,flow"
    # Extra topics to reach 150
    "LDAP Guide|ldap,directory"
    "OAuth2 Guide|oauth2,auth"
    "JWT Tokens|jwt,auth"
    "SAML Guide|saml,auth"
    "OpenID Connect|oidc,auth"
    "Kerberos|kerberos,auth"
    "HashiCorp Vault|vault,secrets"
    "AWS Secrets|aws,secrets"
    "Azure KeyVault|azure,keyvault"
    "GCP Secret Manager|gcp,secrets"
)

for topic_data in "${topics[@]}"; do
    count=$((count + 1))
    IFS='|' read -r topic tags <<< "$topic_data"

    echo "[$count/$total] $topic"

    # Shorter prompt for faster generation
    prompt="Write a concise technical guide about '$topic'. Include: overview, key features, code example, best practices. Markdown format. 5-15KB."

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
generated_by: ollama-qwen2.5-quick
---

# ${topic}

$(cat "/tmp/${topic}.md")

---

## Sources

Generated using Ollama with Qwen2.5-7B model.
EOF

    echo "  ✅ Saved"
    rm "/tmp/${topic}.md"
    sleep 1
    echo ""
done

echo "======================================"
echo "📥 Ingesting into database..."
echo "======================================"

cd "$PROJECT_DIR"
source .venv/bin/activate
python cli.py ingest directory "$OBSIDIAN_DIR"

echo ""
echo "✅ Quick batch complete! Generated $count guides"
