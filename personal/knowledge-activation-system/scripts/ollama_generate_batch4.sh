#!/bin/bash
# Batch 4 - Additional 100 topics
# Usage: ./scripts/ollama_generate_batch4.sh

set -e  # Exit on error

OBSIDIAN_DIR="/Users/d/Obsidian/Knowledge/Notes"
PROJECT_DIR="/Users/d/claude-code/personal/knowledge-activation-system"

echo "🚀 Ollama Batch Content Generator - Batch 4"
echo "==========================================="

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

# Array of topics - Batch 4 (Completely New Topics)
declare -a topics=(
    # CSS Frameworks & Tools
    "Bootstrap 5 Complete Guide 2026|bootstrap,css,framework,responsive"
    "Bulma CSS Framework 2026|bulma,css,framework,flexbox"
    "Foundation CSS Framework 2026|foundation,css,framework,responsive"
    "Material-UI MUI Components 2026|mui,react,material,components"
    "Chakra UI Component Library 2026|chakra,react,components,accessibility"
    "Mantine React Components 2026|mantine,react,components,hooks"
    "Ant Design Components 2026|antd,react,components,enterprise"
    "PrimeReact Component Suite 2026|primereact,react,components,ui"
    "Semantic UI Framework 2026|semantic,ui,framework,components"
    "UIKit Lightweight Framework 2026|uikit,css,framework,lightweight"

    # Static Site Generators
    "Hugo Static Site Generator 2026|hugo,ssg,go,static"
    "Jekyll Static Site Builder 2026|jekyll,ssg,ruby,github"
    "Eleventy 11ty SSG 2026|eleventy,ssg,javascript,jamstack"
    "Hexo Blog Framework 2026|hexo,blog,ssg,nodejs"
    "Pelican Python SSG 2026|pelican,ssg,python,static"
    "Zola Rust SSG 2026|zola,ssg,rust,static"
    "Middleman Ruby SSG 2026|middleman,ssg,ruby,static"
    "Nanoc Static Site Compiler 2026|nanoc,ssg,ruby,static"
    "Bridgetown Modern SSG 2026|bridgetown,ssg,ruby,jamstack"
    "Lume Deno SSG 2026|lume,ssg,deno,static"

    # Headless CMS
    "Strapi Headless CMS 2026|strapi,cms,headless,nodejs"
    "Contentful CMS Platform 2026|contentful,cms,headless,api"
    "Sanity Content Platform 2026|sanity,cms,headless,structured"
    "Prismic Headless CMS 2026|prismic,cms,headless,api"
    "Ghost Headless CMS 2026|ghost,cms,headless,publishing"
    "Directus Data Platform 2026|directus,cms,headless,database"
    "KeystoneJS CMS 2026|keystonejs,cms,graphql,nodejs"
    "Payload CMS TypeScript 2026|payload,cms,headless,typescript"
    "TinaCMS Git-Based 2026|tina,cms,git,markdown"
    "Builder.io Visual CMS 2026|builder,cms,visual,headless"

    # E-Commerce Platforms
    "Shopify Development Guide 2026|shopify,ecommerce,platform,liquid"
    "WooCommerce WordPress 2026|woocommerce,wordpress,ecommerce,php"
    "Magento 2 Development 2026|magento,ecommerce,php,enterprise"
    "BigCommerce Platform 2026|bigcommerce,ecommerce,saas,api"
    "PrestaShop E-Commerce 2026|prestashop,ecommerce,php,opensource"
    "Medusa Commerce Platform 2026|medusa,ecommerce,nodejs,headless"
    "Saleor GraphQL Commerce 2026|saleor,ecommerce,graphql,python"
    "Sylius E-Commerce PHP 2026|sylius,ecommerce,php,symfony"
    "Reaction Commerce Platform 2026|reaction,ecommerce,nodejs,graphql"
    "Vendure Headless Commerce 2026|vendure,ecommerce,typescript,graphql"

    # Email & Communication
    "SendGrid Email API 2026|sendgrid,email,api,transactional"
    "Mailgun Email Service 2026|mailgun,email,api,smtp"
    "Amazon SES Email Service 2026|ses,aws,email,smtp"
    "Postmark Transactional Email 2026|postmark,email,transactional,api"
    "Twilio Communication API 2026|twilio,sms,voice,communication"
    "Vonage Communications 2026|vonage,communication,api,messaging"
    "Plivo Cloud Communication 2026|plivo,communication,voice,sms"
    "MessageBird Omnichannel 2026|messagebird,messaging,omnichannel,api"
    "Stream Chat and Feed 2026|stream,chat,feed,realtime"
    "PubNub Realtime Messaging 2026|pubnub,realtime,messaging,pub-sub"

    # Payment Processing
    "Stripe Payment Platform 2026|stripe,payment,api,processing"
    "PayPal Integration Guide 2026|paypal,payment,integration,api"
    "Square Payment API 2026|square,payment,api,pos"
    "Braintree Payment Gateway 2026|braintree,payment,gateway,paypal"
    "Adyen Payment Platform 2026|adyen,payment,global,processing"
    "Checkout.com Payments 2026|checkout,payment,processing,api"
    "Razorpay Payment Gateway 2026|razorpay,payment,india,gateway"
    "Mollie Payment Service 2026|mollie,payment,europe,api"
    "Paddle Merchant of Record 2026|paddle,payment,saas,billing"
    "Chargebee Subscription 2026|chargebee,subscription,billing,saas"

    # Form Builders & Validation
    "React Hook Form Guide 2026|react-hook-form,forms,react,validation"
    "Formik Form Library 2026|formik,forms,react,validation"
    "Final Form React 2026|final-form,forms,react,state"
    "Yup Validation Schema 2026|yup,validation,schema,javascript"
    "Zod TypeScript Validation 2026|zod,validation,typescript,schema"
    "Joi Validation Library 2026|joi,validation,nodejs,schema"
    "Vest Validation Framework 2026|vest,validation,testing,forms"
    "Vuelidate Vue Validation 2026|vuelidate,validation,vue,forms"
    "VeeValidate Vue Forms 2026|veevalidate,validation,vue,forms"
    "Angular Reactive Forms 2026|angular,forms,reactive,validation"

    # Real-time & WebSockets
    "Socket.io Real-time Engine 2026|socketio,websocket,realtime,nodejs"
    "Ably Realtime Platform 2026|ably,realtime,pub-sub,messaging"
    "Pusher Channels Realtime 2026|pusher,realtime,websocket,channels"
    "Phoenix LiveView Elixir 2026|phoenix,liveview,elixir,realtime"
    "SignalR ASP.NET Realtime 2026|signalr,realtime,aspnet,websocket"
    "Centrifugo Realtime Server 2026|centrifugo,realtime,websocket,server"
    "Mercure Protocol Hub 2026|mercure,protocol,sse,realtime"
    "SSE Server-Sent Events 2026|sse,server-sent,events,realtime"
    "Long Polling Patterns 2026|long-polling,realtime,http,patterns"
    "WebRTC Peer Connection 2026|webrtc,peer,video,realtime"

    # Code Quality & Linting
    "ESLint JavaScript Linter 2026|eslint,linting,javascript,quality"
    "Prettier Code Formatter 2026|prettier,formatting,code,style"
    "Pylint Python Linter 2026|pylint,linting,python,quality"
    "Black Python Formatter 2026|black,formatting,python,pep8"
    "Ruff Fast Python Linter 2026|ruff,linting,python,rust"
    "Rubocop Ruby Linter 2026|rubocop,linting,ruby,style"
    "Clippy Rust Linter 2026|clippy,linting,rust,quality"
    "SwiftLint iOS Linter 2026|swiftlint,linting,swift,ios"
    "ktlint Kotlin Linter 2026|ktlint,linting,kotlin,android"
    "Checkstyle Java Linter 2026|checkstyle,linting,java,quality"

    # Documentation Tools
    "Docusaurus Documentation 2026|docusaurus,documentation,react,static"
    "VuePress Vue Documentation 2026|vuepress,documentation,vue,static"
    "Sphinx Python Docs 2026|sphinx,documentation,python,restructured"
    "MkDocs Material Theme 2026|mkdocs,documentation,markdown,material"
    "GitBook Documentation 2026|gitbook,documentation,markdown,publishing"
    "Slate API Documentation 2026|slate,api,documentation,markdown"
    "Redoc API Documentation 2026|redoc,api,documentation,openapi"
    "Swagger UI OpenAPI 2026|swagger,api,documentation,openapi"
    "Read the Docs Platform 2026|readthedocs,documentation,hosting,sphinx"
    "JSDoc JavaScript Docs 2026|jsdoc,documentation,javascript,api"
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
