#!/usr/bin/env node
/**
 * KAS MCP Server
 *
 * Model Context Protocol server for the Knowledge Activation System.
 * Provides tools to search, ask questions, and capture knowledge directly
 * from Claude Code sessions.
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ToolSchema,
} from '@modelcontextprotocol/sdk/types.js';
import type { z } from 'zod';
import { KASClient } from './kas-client.js';

// Type for MCP Tool definition
type Tool = z.infer<typeof ToolSchema>;

// Initialize KAS client
const kasClient = new KASClient({
  baseUrl: process.env.KAS_API_URL ?? 'http://localhost:8000',
  timeout: 30000,
});

// Tool definitions
const TOOLS: Tool[] = [
  {
    name: 'kas_search',
    description: `Search your personal knowledge base for relevant information.

Use this to find documentation, code examples, notes, and other content you've previously saved.

Examples:
- "How to implement RAG with LlamaIndex"
- "FastAPI dependency injection patterns"
- "Kubernetes deployment strategies"

Supports namespace filtering:
- Exact: namespace="frameworks"
- Prefix: namespace="projects/*" (all projects)

Set rerank=true for higher quality results on complex queries (uses cross-encoder reranking).

Returns ranked results with content snippets and relevance scores.`,
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'The search query - be specific for better results',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of results to return (default: 5, max: 20)',
          default: 5,
        },
        namespace: {
          type: 'string',
          description: 'Filter by namespace (e.g., "frameworks", "projects/*" for prefix match)',
        },
        rerank: {
          type: 'boolean',
          description: 'Apply cross-encoder reranking for better quality (slower but more accurate)',
          default: false,
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'kas_search_project',
    description: `Search within a specific project's knowledge namespace.

Use this when you want to find project-specific learnings, decisions, or patterns.
Automatically scopes search to the project namespace.

Example: Search "authentication flow" in the "voice-ai" project.`,
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'The search query',
        },
        project: {
          type: 'string',
          description: 'Project name (will search in "projects/{project}" namespace)',
        },
        limit: {
          type: 'number',
          description: 'Maximum results (default: 5)',
          default: 5,
        },
      },
      required: ['query', 'project'],
    },
  },
  {
    name: 'kas_ask',
    description: `Ask a question and get a synthesized answer from your knowledge base.

Unlike search, this provides a direct answer by analyzing relevant content
and synthesizing information from multiple sources.

Best for:
- "How does X work?"
- "What's the difference between X and Y?"
- "Explain the process for doing X"

Returns an answer with confidence score and source citations.`,
    inputSchema: {
      type: 'object',
      properties: {
        question: {
          type: 'string',
          description: 'The question to answer',
        },
        context_limit: {
          type: 'number',
          description: 'Number of context chunks to consider (default: 5)',
          default: 5,
        },
      },
      required: ['question'],
    },
  },
  {
    name: 'kas_capture',
    description: `Quickly capture content into your knowledge base for future reference.

Use this to save:
- Code snippets you want to remember
- Important information discovered during coding
- Notes and learnings from the current session
- Architectural decisions and their rationale

The content will be chunked, embedded, and made searchable immediately.

Namespace tips:
- Use "projects/{project-name}" for project-specific knowledge
- Use "patterns" for reusable code patterns
- Use "decisions" for architectural decisions`,
    inputSchema: {
      type: 'object',
      properties: {
        content: {
          type: 'string',
          description: 'The content to save',
        },
        title: {
          type: 'string',
          description: 'A descriptive title for the content',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Optional tags for categorization',
        },
        namespace: {
          type: 'string',
          description: 'Namespace for organization. Use "projects/{name}" for project knowledge, or "quick-capture" for misc.',
          default: 'quick-capture',
        },
        content_type: {
          type: 'string',
          enum: ['note', 'pattern', 'decision', 'snippet'],
          description: 'Type of content being captured',
          default: 'note',
        },
      },
      required: ['content', 'title'],
    },
  },
  {
    name: 'kas_capture_decision',
    description: `Capture an architectural decision (ADR format).

Use this when you've made a significant technical decision:
- Technology choices
- Architecture patterns
- API design decisions
- Trade-off resolutions

The decision will be stored with context, options considered, and rationale.`,
    inputSchema: {
      type: 'object',
      properties: {
        title: {
          type: 'string',
          description: 'Short decision title (e.g., "Use PostgreSQL for persistence")',
        },
        context: {
          type: 'string',
          description: 'What is the issue being decided?',
        },
        decision: {
          type: 'string',
          description: 'What is the decision?',
        },
        rationale: {
          type: 'string',
          description: 'Why was this decision made?',
        },
        alternatives: {
          type: 'array',
          items: { type: 'string' },
          description: 'What alternatives were considered?',
        },
        project: {
          type: 'string',
          description: 'Project this decision belongs to',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for categorization',
        },
      },
      required: ['title', 'context', 'decision', 'rationale'],
    },
  },
  {
    name: 'kas_stats',
    description: `Get statistics about your knowledge base.

Returns:
- Total documents stored
- Total chunks indexed
- System health status`,
    inputSchema: {
      type: 'object',
      properties: {},
    },
  },
  {
    name: 'kas_capture_pattern',
    description: `Capture a reusable code pattern.

Use this to save code patterns you want to reuse across projects:
- Utility functions
- Common patterns (factory, singleton, etc.)
- API integration snippets
- Error handling patterns

The pattern will be searchable by language and use case.`,
    inputSchema: {
      type: 'object',
      properties: {
        name: {
          type: 'string',
          description: 'Pattern name (e.g., "Async Retry with Backoff")',
        },
        language: {
          type: 'string',
          description: 'Programming language (e.g., "python", "typescript")',
        },
        code: {
          type: 'string',
          description: 'The code pattern',
        },
        description: {
          type: 'string',
          description: 'When to use this pattern',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for categorization',
        },
      },
      required: ['name', 'language', 'code', 'description'],
    },
  },
  {
    name: 'kas_search_patterns',
    description: `Search for code patterns in your knowledge base.

Find reusable code patterns by language or use case.
Example: "retry pattern typescript" or "factory python"`,
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query (e.g., "async retry", "factory pattern")',
        },
        language: {
          type: 'string',
          description: 'Filter by language (optional)',
        },
        limit: {
          type: 'number',
          description: 'Max results (default: 5)',
          default: 5,
        },
      },
      required: ['query'],
    },
  },
  {
    name: 'kas_ingest',
    description: `Ingest external content into your knowledge base.

Supports:
- YouTube videos (transcripts)
- Web pages/bookmarks (article extraction)
- URLs with auto-title detection

The content will be chunked, embedded, and made searchable.`,
    inputSchema: {
      type: 'object',
      properties: {
        type: {
          type: 'string',
          enum: ['youtube', 'bookmark', 'url'],
          description: 'Type of content to ingest',
        },
        source: {
          type: 'string',
          description: 'URL or video ID to ingest',
        },
        title: {
          type: 'string',
          description: 'Optional title override',
        },
        namespace: {
          type: 'string',
          description: 'Namespace for organization',
        },
        tags: {
          type: 'array',
          items: { type: 'string' },
          description: 'Tags for categorization',
        },
      },
      required: ['type', 'source'],
    },
  },
  {
    name: 'kas_review',
    description: `Interact with the spaced repetition review system.

Actions:
- "get": Get items due for review
- "submit": Submit a review rating for an item

Ratings: 1=Again (forgot), 2=Hard, 3=Good, 4=Easy`,
    inputSchema: {
      type: 'object',
      properties: {
        action: {
          type: 'string',
          enum: ['get', 'submit', 'stats'],
          description: 'Action to perform',
        },
        content_id: {
          type: 'string',
          description: 'Content ID (required for submit)',
        },
        rating: {
          type: 'number',
          minimum: 1,
          maximum: 4,
          description: 'Rating 1-4 (required for submit)',
        },
        limit: {
          type: 'number',
          description: 'Max items to return for get (default: 5)',
          default: 5,
        },
      },
      required: ['action'],
    },
  },
];

// Create MCP server
const server = new Server(
  {
    name: 'kas-mcp-server',
    version: '1.0.0',
  },
  {
    capabilities: {
      tools: {},
    },
  }
);

// Handle tool listing
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return { tools: TOOLS };
});

// Handle tool execution
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    switch (name) {
      case 'kas_search': {
        const { query, limit = 5, namespace, rerank = false } = args as {
          query: string;
          limit?: number;
          namespace?: string;
          rerank?: boolean;
        };

        const results = await kasClient.search(query, {
          limit: Math.min(limit, 20),
          namespace,
          rerank,
        });

        if (results.results.length === 0) {
          return {
            content: [
              {
                type: 'text',
                text: `No results found for "${query}". Try:\n- Using different keywords\n- Broadening your search\n- Checking if the content has been ingested`,
              },
            ],
          };
        }

        const formattedResults = results.results
          .map((r, i) => {
            const ns = r.namespace || 'default';
            const content = r.chunk_text || '';
            const simScore = r.vector_similarity ? `${(r.vector_similarity * 100).toFixed(0)}%` : 'N/A';
            return `### ${i + 1}. ${r.title}\n**Namespace:** ${ns} | **Similarity:** ${simScore}\n\n${content.slice(0, 500)}${content.length > 500 ? '...' : ''}`;
          })
          .join('\n\n---\n\n');

        const rerankInfo = results.reranked ? ' [reranked]' : '';
        return {
          content: [
            {
              type: 'text',
              text: `## Search Results for "${query}"${namespace ? ` (namespace: ${namespace})` : ''}${rerankInfo}\n\nFound ${results.total} results:\n\n${formattedResults}`,
            },
          ],
        };
      }

      case 'kas_search_project': {
        const { query, project, limit = 5 } = args as {
          query: string;
          project: string;
          limit?: number;
        };

        const projectNamespace = `projects/${project}`;
        const results = await kasClient.search(query, {
          limit: Math.min(limit, 20),
          namespace: projectNamespace,
        });

        if (results.results.length === 0) {
          // Try prefix match as fallback
          const prefixResults = await kasClient.search(query, {
            limit: Math.min(limit, 20),
            namespace: `${projectNamespace}*`,
          });

          if (prefixResults.results.length === 0) {
            return {
              content: [
                {
                  type: 'text',
                  text: `No results found for "${query}" in project "${project}".\n\nThe project namespace "projects/${project}" may not have any content yet.\nUse kas_capture with namespace="projects/${project}" to add knowledge.`,
                },
              ],
            };
          }

          const formattedResults = prefixResults.results
            .map((r, i) => {
              const content = r.chunk_text || '';
              return `### ${i + 1}. ${r.title}\n**Namespace:** ${r.namespace || 'default'}\n\n${content.slice(0, 400)}${content.length > 400 ? '...' : ''}`;
            })
            .join('\n\n---\n\n');

          return {
            content: [
              {
                type: 'text',
                text: `## Project Knowledge: ${project}\n\nFound ${prefixResults.total} results:\n\n${formattedResults}`,
              },
            ],
          };
        }

        const formattedResults = results.results
          .map((r, i) => {
            const content = r.chunk_text || '';
            return `### ${i + 1}. ${r.title}\n\n${content.slice(0, 400)}${content.length > 400 ? '...' : ''}`;
          })
          .join('\n\n---\n\n');

        return {
          content: [
            {
              type: 'text',
              text: `## Project Knowledge: ${project}\n\nFound ${results.total} results:\n\n${formattedResults}`,
            },
          ],
        };
      }

      case 'kas_ask': {
        const { question, context_limit = 5 } = args as {
          question: string;
          context_limit?: number;
        };

        const response = await kasClient.ask(question, { context_limit });

        const confidenceLabel =
          response.confidence_score > 0.7
            ? '**High**'
            : response.confidence_score > 0.4
              ? '**Medium**'
              : '**Low** (answer may be incomplete)';

        const citations =
          response.citations.length > 0
            ? response.citations
                .map((c) => `${c.index}. **${c.title}** (${c.content_type})\n   ${c.chunk_text.slice(0, 200)}...`)
                .join('\n\n')
            : 'No citations found';

        // Handle case where AI synthesis failed but we have citations
        if (response.error && !response.answer) {
          return {
            content: [
              {
                type: 'text',
                text: `## Relevant Sources Found\n\n*AI synthesis unavailable: ${response.error}*\n\n**Confidence:** ${confidenceLabel} (${(response.confidence_score * 100).toFixed(0)}%)\n\n### Citations:\n${citations}\n\n---\n*To enable AI-synthesized answers, configure OPENROUTER_API_KEY in the KAS environment.*`,
              },
            ],
          };
        }

        return {
          content: [
            {
              type: 'text',
              text: `## Answer\n\n${response.answer}\n\n---\n**Confidence:** ${confidenceLabel} (${(response.confidence_score * 100).toFixed(0)}%)\n\n### Sources:\n${citations}`,
            },
          ],
        };
      }

      case 'kas_capture': {
        const { content, title, tags = [], namespace = 'quick-capture', content_type = 'note' } =
          args as {
            content: string;
            title: string;
            tags?: string[];
            namespace?: string;
            content_type?: string;
          };

        const response = await kasClient.ingest(content, {
          title,
          tags: [...tags, content_type],
          namespace,
          source: 'claude-code-mcp',
          document_type: content_type === 'snippet' ? 'code' : 'markdown',
        });

        return {
          content: [
            {
              type: 'text',
              text: `**Captured successfully!**\n\n- **Title:** ${title}\n- **Type:** ${content_type}\n- **Namespace:** ${response.namespace}\n- **Chunks created:** ${response.chunks_created}\n- **Content ID:** ${response.content_id}`,
            },
          ],
        };
      }

      case 'kas_capture_decision': {
        const { title, context, decision, rationale, alternatives = [], project, tags = [] } =
          args as {
            title: string;
            context: string;
            decision: string;
            rationale: string;
            alternatives?: string[];
            project?: string;
            tags?: string[];
          };

        // Build ADR-format content
        const adrContent = `# ${title}

## Status
Accepted

## Context
${context}

## Decision
${decision}

## Rationale
${rationale}

${alternatives.length > 0 ? `## Alternatives Considered\n${alternatives.map((a, i) => `${i + 1}. ${a}`).join('\n')}` : ''}
`;

        const namespace = project ? `projects/${project}/decisions` : 'decisions';
        const allTags = ['decision', 'adr', ...tags];
        if (project) allTags.push(project);

        const response = await kasClient.ingest(adrContent, {
          title: `ADR: ${title}`,
          tags: allTags,
          namespace,
          source: 'claude-code-mcp',
        });

        return {
          content: [
            {
              type: 'text',
              text: `**Decision Recorded!**\n\n- **Title:** ${title}\n- **Project:** ${project || 'N/A'}\n- **Namespace:** ${response.namespace}\n- **Content ID:** ${response.content_id}\n\nThis decision is now searchable. Use \`kas_search "decision ${title.split(' ')[0]}"\` to find it later.`,
            },
          ],
        };
      }

      case 'kas_stats': {
        const health = await kasClient.health();

        return {
          content: [
            {
              type: 'text',
              text: `## Knowledge Base Statistics\n\n- **Status:** ${health.status}\n- **Version:** ${health.version}\n- **Total Documents:** ${health.stats.total_content}\n- **Total Chunks:** ${health.stats.total_chunks}\n- **Database:** ${health.services.database}\n- **Embeddings:** ${health.services.embeddings}`,
            },
          ],
        };
      }

      case 'kas_capture_pattern': {
        const { name, language, code, description, tags = [] } = args as {
          name: string;
          language: string;
          code: string;
          description: string;
          tags?: string[];
        };

        // Build pattern content with metadata
        const patternContent = `# ${name}

**Language:** ${language}
**Use Case:** ${description}

## Code

\`\`\`${language}
${code}
\`\`\`

## When to Use

${description}
`;

        const allTags = ['pattern', language, ...tags];

        const response = await kasClient.ingest(patternContent, {
          title: `Pattern: ${name} (${language})`,
          tags: allTags,
          namespace: 'patterns',
          document_type: 'code',
          source: 'claude-code-mcp',
        });

        return {
          content: [
            {
              type: 'text',
              text: `**Pattern Saved!**\n\n- **Name:** ${name}\n- **Language:** ${language}\n- **Namespace:** patterns\n- **Content ID:** ${response.content_id}\n\nSearch with: \`kas_search_patterns "${name.split(' ')[0]}"\``,
            },
          ],
        };
      }

      case 'kas_search_patterns': {
        const { query, language, limit = 5 } = args as {
          query: string;
          language?: string;
          limit?: number;
        };

        // Build search query
        const searchQuery = language ? `${query} ${language} pattern` : `${query} pattern`;

        const results = await kasClient.search(searchQuery, {
          limit: Math.min(limit, 20),
          namespace: 'patterns',
        });

        if (results.results.length === 0) {
          // Try broader search without namespace filter
          const broaderResults = await kasClient.search(searchQuery, {
            limit: Math.min(limit, 20),
          });

          const patternResults = broaderResults.results.filter(
            r => r.namespace === 'patterns' || (r.chunk_text && r.chunk_text.includes('```'))
          );

          if (patternResults.length === 0) {
            return {
              content: [
                {
                  type: 'text',
                  text: `No patterns found for "${query}"${language ? ` in ${language}` : ''}.\n\nUse \`kas_capture_pattern\` to save patterns for future use.`,
                },
              ],
            };
          }

          const formattedResults = patternResults
            .slice(0, limit)
            .map((r, i) => {
              const content = r.chunk_text || '';
              return `### ${i + 1}. ${r.title}\n\n${content.slice(0, 600)}${content.length > 600 ? '...' : ''}`;
            })
            .join('\n\n---\n\n');

          return {
            content: [
              {
                type: 'text',
                text: `## Patterns for "${query}"\n\n${formattedResults}`,
              },
            ],
          };
        }

        const formattedResults = results.results
          .map((r, i) => {
            const content = r.chunk_text || '';
            return `### ${i + 1}. ${r.title}\n\n${content.slice(0, 600)}${content.length > 600 ? '...' : ''}`;
          })
          .join('\n\n---\n\n');

        return {
          content: [
            {
              type: 'text',
              text: `## Patterns for "${query}"${language ? ` (${language})` : ''}\n\nFound ${results.total} patterns:\n\n${formattedResults}`,
            },
          ],
        };
      }

      case 'kas_ingest': {
        const { type, source, title, namespace, tags = [] } = args as {
          type: 'youtube' | 'bookmark' | 'url';
          source: string;
          title?: string;
          namespace?: string;
          tags?: string[];
        };

        const response = await kasClient.ingestExternal(type, source, {
          title,
          namespace,
          tags,
        });

        return {
          content: [
            {
              type: 'text',
              text: `**Ingested successfully!**\n\n- **Type:** ${type}\n- **Title:** ${response.title}\n- **Namespace:** ${response.namespace}\n- **Chunks created:** ${response.chunks_created}\n- **Content ID:** ${response.content_id}`,
            },
          ],
        };
      }

      case 'kas_review': {
        const { action, content_id, rating, limit = 5 } = args as {
          action: 'get' | 'submit' | 'stats';
          content_id?: string;
          rating?: number;
          limit?: number;
        };

        if (action === 'get') {
          const items = await kasClient.getReviewItems(limit);

          if (items.length === 0) {
            return {
              content: [
                {
                  type: 'text',
                  text: '**No items due for review!** Great job staying on top of your reviews.',
                },
              ],
            };
          }

          const formattedItems = items
            .map((item, i) => {
              const state = item.is_new ? 'New' : item.is_learning ? 'Learning' : 'Review';
              return `### ${i + 1}. ${item.title}\n**Type:** ${item.content_type} | **State:** ${state} | **Reps:** ${item.reps}\n**ID:** \`${item.content_id}\`\n\n${item.preview_text?.slice(0, 200) || ''}...`;
            })
            .join('\n\n---\n\n');

          return {
            content: [
              {
                type: 'text',
                text: `## Items Due for Review (${items.length})\n\n${formattedItems}\n\n---\n*Use \`kas_review\` with action="submit" to rate an item.*`,
              },
            ],
          };
        }

        if (action === 'submit') {
          if (!content_id || !rating) {
            return {
              content: [
                {
                  type: 'text',
                  text: '**Error:** content_id and rating are required for submit action.',
                },
              ],
              isError: true,
            };
          }

          const result = await kasClient.submitReview(content_id, rating);

          const ratingLabels: Record<number, string> = {
            1: 'Again',
            2: 'Hard',
            3: 'Good',
            4: 'Easy',
          };

          return {
            content: [
              {
                type: 'text',
                text: `**Review submitted!**\n\n- **Rating:** ${ratingLabels[rating]} (${rating})\n- **Next review:** ${result.next_review}\n- **New state:** ${result.new_state}`,
              },
            ],
          };
        }

        if (action === 'stats') {
          const stats = await kasClient.getReviewStats();

          return {
            content: [
              {
                type: 'text',
                text: `## Review Statistics\n\n- **Due now:** ${stats.due_now}\n- **New items:** ${stats.new}\n- **Learning:** ${stats.learning}\n- **Review:** ${stats.review}\n- **Total active:** ${stats.total_active}\n- **Reviewed today:** ${stats.reviews_today}`,
              },
            ],
          };
        }

        return {
          content: [
            {
              type: 'text',
              text: `Unknown action: ${action}`,
            },
          ],
          isError: true,
        };
      }

      default:
        return {
          content: [
            {
              type: 'text',
              text: `Unknown tool: ${name}`,
            },
          ],
          isError: true,
        };
    }
  } catch (error) {
    const errorMessage =
      error instanceof Error ? error.message : 'Unknown error';

    // Check if KAS is down
    if (
      errorMessage.includes('ECONNREFUSED') ||
      errorMessage.includes('fetch failed')
    ) {
      return {
        content: [
          {
            type: 'text',
            text: `**KAS API is not available.**\n\nMake sure the Knowledge Activation System is running:\n\`\`\`bash\ncd /Users/d/claude-code/personal/knowledge-activation-system\nuv run uvicorn knowledge.api.main:app --host 0.0.0.0 --port 8000\n\`\`\``,
          },
        ],
        isError: true,
      };
    }

    return {
      content: [
        {
          type: 'text',
          text: `**Error:** ${errorMessage}`,
        },
      ],
      isError: true,
    };
  }
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('KAS MCP Server running on stdio');
}

main().catch((error) => {
  console.error('Fatal error:', error);
  process.exit(1);
});
