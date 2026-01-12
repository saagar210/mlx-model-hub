#!/bin/bash
# Batch 5 - Fast 50 topics to reach 1,000
# Usage: ./scripts/ollama_generate_batch5.sh

set -e

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"
PROJECT_DIR="/Users/d/claude-code/personal/knowledge-activation-system"

echo "🚀 Ollama Batch 5 - Fast Track to 1,000"
echo "======================================"

if ! pgrep -x "ollama" > /dev/null; then
    ollama serve &
    sleep 5
fi

echo "📥 Model ready..."
ollama pull qwen2.5:7b > /dev/null 2>&1

echo "📚 Generating 50 guides..."
echo ""

count=0
total=50

declare -a topics=(
    # Cloud Services
    "AWS S3 Storage Guide 2026|aws,s3,storage,cloud"
    "AWS EC2 Compute Guide 2026|aws,ec2,compute,cloud"
    "AWS RDS Database Service 2026|aws,rds,database,cloud"
    "Azure Blob Storage 2026|azure,storage,blob,cloud"
    "Azure Functions Serverless 2026|azure,functions,serverless,cloud"
    "Google Cloud Run 2026|gcp,cloud-run,containers,serverless"
    "Google Cloud Storage 2026|gcp,storage,cloud,buckets"
    "DigitalOcean Droplets 2026|digitalocean,vps,cloud,hosting"
    "Linode Cloud Computing 2026|linode,cloud,vps,hosting"
    "Vultr Cloud Hosting 2026|vultr,cloud,vps,hosting"

    # Programming Patterns
    "Design Patterns Gang of Four 2026|design-patterns,oop,architecture,gof"
    "SOLID Principles Guide 2026|solid,oop,principles,architecture"
    "Clean Code Principles 2026|clean-code,best-practices,programming,quality"
    "Refactoring Patterns 2026|refactoring,patterns,code-quality,maintenance"
    "Dependency Injection Patterns 2026|di,patterns,architecture,testing"
    "Repository Pattern Guide 2026|repository,pattern,data-access,architecture"
    "Factory Pattern Implementation 2026|factory,pattern,creational,design"
    "Observer Pattern Guide 2026|observer,pattern,behavioral,events"
    "Strategy Pattern Implementation 2026|strategy,pattern,behavioral,polymorphism"
    "Decorator Pattern Guide 2026|decorator,pattern,structural,composition"

    # DevOps Tools
    "Vagrant Development Environments 2026|vagrant,development,vm,devops"
    "Packer Image Builder 2026|packer,images,automation,hashicorp"
    "Helm Kubernetes Packaging 2026|helm,kubernetes,packaging,charts"
    "Kustomize Kubernetes Config 2026|kustomize,kubernetes,configuration,gitops"
    "Skaffold Development Workflow 2026|skaffold,kubernetes,development,workflow"
    "Tilt Development Environment 2026|tilt,kubernetes,development,local"
    "Podman Container Tool 2026|podman,containers,docker,alternative"
    "Buildah Container Images 2026|buildah,containers,images,build"
    "OpenShift Container Platform 2026|openshift,kubernetes,redhat,platform"
    "Rancher Kubernetes Management 2026|rancher,kubernetes,management,platform"

    # Security Tools
    "Let's Encrypt SSL Certificates 2026|letsencrypt,ssl,certificates,security"
    "Certbot SSL Automation 2026|certbot,ssl,automation,letsencrypt"
    "Fail2ban Intrusion Prevention 2026|fail2ban,security,ips,protection"
    "UFW Firewall Guide 2026|ufw,firewall,security,ubuntu"
    "iptables Firewall Rules 2026|iptables,firewall,linux,networking"
    "SELinux Security Guide 2026|selinux,security,linux,access-control"
    "AppArmor Security Profiles 2026|apparmor,security,linux,mandatory-access"
    "OpenVPN Setup Guide 2026|openvpn,vpn,security,networking"
    "WireGuard VPN Modern 2026|wireguard,vpn,security,performance"
    "Tailscale Mesh VPN 2026|tailscale,vpn,mesh,zero-trust"

    # Database Tools
    "pgAdmin PostgreSQL GUI 2026|pgadmin,postgresql,gui,database"
    "DataGrip Database IDE 2026|datagrip,database,ide,jetbrains"
    "TablePlus Database Client 2026|tableplus,database,client,gui"
    "DBeaver Universal Tool 2026|dbeaver,database,universal,client"
    "Flyway Database Migrations 2026|flyway,migrations,database,versioning"
    "Liquibase Change Management 2026|liquibase,migrations,database,changelog"
    "Prisma ORM TypeScript 2026|prisma,orm,typescript,database"
    "TypeORM TypeScript ORM 2026|typeorm,orm,typescript,database"
    "Drizzle ORM TypeScript 2026|drizzle,orm,typescript,performance"
    "Sequelize Node.js ORM 2026|sequelize,orm,nodejs,database"
)

for topic_data in "${topics[@]}"; do
    count=$((count + 1))
    IFS='|' read -r topic tags <<< "$topic_data"
    
    echo "[$count/$total] $topic"
    
    prompt="Create a comprehensive technical guide about '$topic'. Include: clear sections, code examples with comments, best practices, common patterns, performance tips, security considerations, and a best practices summary. Format in markdown. Make it detailed (40-80KB)."
    
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
generated_by: ollama-qwen2.5-batch5
---

# ${topic}

$(cat "/tmp/${topic}.md")

---

## Sources

Generated using Ollama with Qwen2.5-7B model.
EOF
    
    echo "  ✅ Saved"
    rm "/tmp/${topic}.md"
    sleep 2  # Faster rate limiting
    echo ""
done

echo "======================================"
echo "📥 Ingesting into database..."
echo "======================================"

cd "$PROJECT_DIR"
source .venv/bin/activate
python cli.py ingest directory "$OBSIDIAN_DIR"

echo ""
echo "✅ Batch 5 complete! Generated $count guides"
