#!/bin/bash
# Simple batch content generator using Ollama CLI
# Usage: ./scripts/ollama_generate.sh

set -e  # Exit on error

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"
PROJECT_DIR="/Users/d/claude-code/personal/knowledge-activation-system"

echo "🚀 Ollama Batch Content Generator"
echo "=================================="

# Check if Ollama is running
if ! pgrep -x "ollama" > /dev/null; then
    echo "Starting Ollama server..."
    ollama serve &
    sleep 5
fi

# Pull model if not exists
echo "📥 Ensuring Qwen2.5 model is available..."
ollama pull qwen2.5:7b

echo ""
echo "📚 Generating reference guides..."
echo ""

# Counter
count=0
total=100

# Array of topics - Batch 4 (New Topics)
declare -a topics=(
    # Frontend Libraries & Frameworks
    "Preact Lightweight React 2026|preact,react,frontend,lightweight"
    "Lit Web Components 2026|lit,web-components,javascript,frontend"
    "Alpine.js Minimal Framework 2026|alpinejs,javascript,frontend,minimal"
    "HTMX Modern HTML 2026|htmx,html,frontend,hypermedia"
    "Stimulus JavaScript Framework 2026|stimulus,javascript,frontend,hotwire"
    "Ember.js Framework Guide 2026|emberjs,javascript,frontend,spa"
    "Backbone.js Patterns 2026|backbonejs,javascript,frontend,mvc"
    "Aurelia Framework Guide 2026|aurelia,javascript,frontend,spa"
    "Mithril.js Lightweight MVC 2026|mithriljs,javascript,frontend,mvc"
    "Inferno React Alternative 2026|inferno,react,frontend,performance"

    # Message Queues & Streaming
    "RabbitMQ Message Broker 2026|rabbitmq,messaging,queue,amqp"
    "Apache Pulsar Streaming 2026|pulsar,streaming,messaging,events"
    "NATS Messaging System 2026|nats,messaging,cloud-native,microservices"
    "Amazon SQS and SNS Guide 2026|aws,sqs,sns,messaging"
    "Azure Service Bus Guide 2026|azure,service-bus,messaging,cloud"

    # Search & Analytics
    "Apache Solr Search Platform 2026|solr,search,apache,indexing"
    "Algolia Search Service 2026|algolia,search,saas,indexing"
    "Meilisearch Fast Search 2026|meilisearch,search,rust,indexing"
    "Typesense Search Engine 2026|typesense,search,typo-tolerance,indexing"
    "Apache Druid Analytics 2026|druid,analytics,olap,timeseries"

    # Caching & In-Memory
    "Memcached Caching System 2026|memcached,caching,distributed,memory"
    "Varnish HTTP Cache 2026|varnish,caching,http,cdn"
    "Hazelcast In-Memory Grid 2026|hazelcast,in-memory,distributed,cache"
    "Apache Ignite Platform 2026|ignite,in-memory,distributed,computing"
    "KeyDB High Performance Redis 2026|keydb,redis,cache,database"

    # API & Integration
    "gRPC Service Communication 2026|grpc,rpc,api,microservices"
    "Protocol Buffers Guide 2026|protobuf,serialization,api,data"
    "Apache Thrift RPC Framework 2026|thrift,rpc,api,serialization"
    "REST API Design Best Practices 2026|rest,api,design,http"
    "OpenAPI Specification Guide 2026|openapi,swagger,api,documentation"

    # Authentication & Security
    "OAuth2 and OpenID Connect 2026|oauth2,oidc,authentication,security"
    "JSON Web Tokens JWT Guide 2026|jwt,tokens,authentication,security"
    "Auth0 Authentication Platform 2026|auth0,authentication,identity,saas"
    "Keycloak Identity Management 2026|keycloak,identity,sso,authentication"
    "HashiCorp Vault Secrets 2026|vault,secrets,security,hashicorp"

    # Container Orchestration
    "Docker Swarm Orchestration 2026|docker,swarm,orchestration,containers"
    "Nomad Cluster Scheduler 2026|nomad,scheduler,orchestration,hashicorp"
    "Amazon ECS Container Service 2026|ecs,aws,containers,orchestration"
    "Google Kubernetes Engine GKE 2026|gke,kubernetes,google,cloud"
    "Azure Kubernetes Service AKS 2026|aks,kubernetes,azure,cloud"

    # Service Mesh & Networking
    "Linkerd Service Mesh 2026|linkerd,service-mesh,kubernetes,networking"
    "Consul Service Discovery 2026|consul,service-discovery,hashicorp,networking"
    "Envoy Proxy Guide 2026|envoy,proxy,service-mesh,networking"
    "Traefik Reverse Proxy 2026|traefik,proxy,load-balancer,networking"
    "NGINX Advanced Configuration 2026|nginx,web-server,proxy,performance"

    # Monitoring & Logging
    "Grafana Visualization Platform 2026|grafana,monitoring,visualization,metrics"
    "Prometheus Monitoring System 2026|prometheus,monitoring,metrics,timeseries"
    "ELK Stack Elasticsearch Logstash Kibana 2026|elk,logging,elasticsearch,analytics"
    "Datadog Monitoring Platform 2026|datadog,monitoring,apm,saas"
    "New Relic APM Guide 2026|newrelic,apm,monitoring,performance"

    # CI/CD & Automation
    "CircleCI Pipeline Guide 2026|circleci,cicd,automation,testing"
    "Travis CI Configuration 2026|travis,cicd,automation,github"
    "Drone CI Self-Hosted 2026|drone,cicd,self-hosted,containers"
    "ArgoCD GitOps Deployment 2026|argocd,gitops,kubernetes,deployment"
    "Flux GitOps Toolkit 2026|flux,gitops,kubernetes,automation"

    # Frontend Build Tools
    "Webpack 5 Configuration 2026|webpack,bundler,javascript,build"
    "Vite Build Tool Guide 2026|vite,bundler,esm,build"
    "Rollup Bundler Guide 2026|rollup,bundler,esm,build"
    "esbuild Fast Bundler 2026|esbuild,bundler,go,build"
    "Parcel Zero Config Bundler 2026|parcel,bundler,zero-config,build"

    # Mobile Development
    "SwiftUI Complete Guide 2026|swiftui,ios,apple,mobile"
    "Jetpack Compose Android 2026|compose,android,kotlin,mobile"
    "Flutter State Management 2026|flutter,state-management,dart,mobile"
    "React Native Navigation 2026|react-native,navigation,mobile,javascript"
    "Expo Development Platform 2026|expo,react-native,mobile,development"

    # Data Processing
    "Apache Spark Big Data 2026|spark,big-data,processing,analytics"
    "Apache Flink Stream Processing 2026|flink,streaming,processing,real-time"
    "Apache Beam Unified Processing 2026|beam,data-processing,batch,streaming"
    "Airflow Workflow Orchestration 2026|airflow,workflow,orchestration,etl"
    "Prefect Workflow Engine 2026|prefect,workflow,python,orchestration"

    # Machine Learning Ops
    "MLflow ML Lifecycle 2026|mlflow,mlops,machine-learning,lifecycle"
    "Kubeflow ML Platform 2026|kubeflow,kubernetes,ml,platform"
    "DVC Data Version Control 2026|dvc,version-control,data,ml"
    "Weights and Biases Tracking 2026|wandb,experiment,tracking,ml"
    "MLOps Best Practices 2026|mlops,machine-learning,operations,devops"

    # Cloud Native
    "Cloud Native Patterns 2026|cloud-native,patterns,architecture,kubernetes"
    "Serverless Framework Guide 2026|serverless,framework,aws,lambda"
    "OpenFaaS Functions as a Service 2026|openfaas,faas,serverless,kubernetes"
    "Knative Serverless Platform 2026|knative,serverless,kubernetes,events"
    "Dapr Distributed Application Runtime 2026|dapr,microservices,runtime,cloud-native"

    # Web Performance
    "CDN Content Delivery Networks 2026|cdn,performance,networking,web"
    "Cloudflare Workers Edge Computing 2026|cloudflare,edge,serverless,workers"
    "Web Vitals Optimization 2026|web-vitals,performance,frontend,metrics"
    "Progressive Web Apps PWA 2026|pwa,web,mobile,progressive"
    "Service Workers Advanced Guide 2026|service-workers,pwa,caching,web"

    # Specialized Databases
    "CockroachDB Distributed SQL 2026|cockroachdb,distributed,sql,database"
    "DynamoDB NoSQL Database 2026|dynamodb,nosql,aws,database"
    "FaunaDB Serverless Database 2026|faunadb,serverless,database,graphql"
    "InfluxDB Time Series 2026|influxdb,timeseries,monitoring,database"
    "ScyllaDB High Performance 2026|scylladb,nosql,cassandra,database"

    # Developer Tools
    "Postman API Testing 2026|postman,api,testing,development"
    "Insomnia REST Client 2026|insomnia,rest,api,testing"
    "Bruno API Client 2026|bruno,api,testing,client"
    "HTTPie Command Line HTTP 2026|httpie,cli,http,api"
    "Curl Advanced Usage 2026|curl,cli,http,networking"
)

for topic_data in "${topics[@]}"; do
    count=$((count + 1))

    # Split topic and tags
    IFS='|' read -r topic tags <<< "$topic_data"

    echo "[$count/$total] $topic"

    # Create prompt
    prompt="Create a comprehensive technical reference guide about '$topic'.

Include:
- Clear section headers
- Practical code examples with comments
- Best practices
- Common patterns and use cases
- Performance considerations
- Security considerations
- A summary of best practices

Format in markdown. Make it detailed and comprehensive (aim for 40-80KB)."

    # Generate content with Ollama (redirect stderr to hide model loading messages)
    echo "  📝 Generating content..."
    ollama run qwen2.5:7b "$prompt" 2>/dev/null > "/tmp/${topic}.md"

    # Check if file was created and has content
    if [ ! -s "/tmp/${topic}.md" ]; then
        echo "  ❌ Failed to generate content"
        continue
    fi

    # Add YAML frontmatter
    cat > "$OBSIDIAN_DIR/${topic}.md" << EOF
---
type: reference
tags: [${tags}]
captured_at: '$(date +%Y-%m-%d)'
generated_by: ollama-qwen2.5
---

# ${topic}

$(cat "/tmp/${topic}.md")

---

## Sources

Generated using Ollama with Qwen2.5-7B model.
EOF

    echo "  ✅ Saved: ${topic}.md"

    # Cleanup temp file
    rm "/tmp/${topic}.md"

    # Rate limiting to avoid overwhelming system
    sleep 3

    echo ""
done

echo "=================================="
echo "📥 Running database ingestion..."
echo "=================================="

cd "$PROJECT_DIR"
source .venv/bin/activate
python cli.py ingest directory "$OBSIDIAN_DIR"

echo ""
echo "✅ Batch generation complete!"
echo "   Generated $count reference guides"
