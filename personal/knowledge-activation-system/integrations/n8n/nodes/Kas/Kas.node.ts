import {
  IExecuteFunctions,
  INodeExecutionData,
  INodeType,
  INodeTypeDescription,
  NodeOperationError,
} from 'n8n-workflow';

export class Kas implements INodeType {
  description: INodeTypeDescription = {
    displayName: 'KAS',
    name: 'kas',
    icon: 'file:kas.svg',
    group: ['transform'],
    version: 1,
    subtitle: '={{$parameter["operation"]}}',
    description: 'Interact with Knowledge Activation System',
    defaults: {
      name: 'KAS',
    },
    inputs: ['main'],
    outputs: ['main'],
    credentials: [
      {
        name: 'kasApi',
        required: true,
      },
    ],
    properties: [
      {
        displayName: 'Operation',
        name: 'operation',
        type: 'options',
        noDataExpression: true,
        options: [
          {
            name: 'Search',
            value: 'search',
            description: 'Search the knowledge base',
            action: 'Search the knowledge base',
          },
          {
            name: 'Capture',
            value: 'capture',
            description: 'Capture content to knowledge base',
            action: 'Capture content to knowledge base',
          },
          {
            name: 'Get Stats',
            value: 'stats',
            description: 'Get knowledge base statistics',
            action: 'Get knowledge base statistics',
          },
          {
            name: 'Get Content',
            value: 'getContent',
            description: 'Get content by ID',
            action: 'Get content by ID',
          },
        ],
        default: 'search',
      },
      // Search parameters
      {
        displayName: 'Query',
        name: 'query',
        type: 'string',
        default: '',
        required: true,
        displayOptions: {
          show: {
            operation: ['search'],
          },
        },
        description: 'Search query',
      },
      {
        displayName: 'Limit',
        name: 'limit',
        type: 'number',
        default: 10,
        displayOptions: {
          show: {
            operation: ['search'],
          },
        },
        description: 'Maximum number of results',
      },
      {
        displayName: 'Namespace',
        name: 'namespace',
        type: 'string',
        default: '',
        displayOptions: {
          show: {
            operation: ['search'],
          },
        },
        description: 'Filter by namespace (optional)',
      },
      // Capture parameters
      {
        displayName: 'Text',
        name: 'text',
        type: 'string',
        default: '',
        required: true,
        displayOptions: {
          show: {
            operation: ['capture'],
          },
        },
        description: 'Text content to capture',
      },
      {
        displayName: 'Title',
        name: 'title',
        type: 'string',
        default: '',
        displayOptions: {
          show: {
            operation: ['capture'],
          },
        },
        description: 'Title for the captured content',
      },
      {
        displayName: 'Tags',
        name: 'tags',
        type: 'string',
        default: '',
        displayOptions: {
          show: {
            operation: ['capture'],
          },
        },
        description: 'Comma-separated tags',
      },
      // Get Content parameters
      {
        displayName: 'Content ID',
        name: 'contentId',
        type: 'string',
        default: '',
        required: true,
        displayOptions: {
          show: {
            operation: ['getContent'],
          },
        },
        description: 'Content UUID',
      },
    ],
  };

  async execute(this: IExecuteFunctions): Promise<INodeExecutionData[][]> {
    const items = this.getInputData();
    const returnData: INodeExecutionData[] = [];
    const credentials = await this.getCredentials('kasApi');
    const baseUrl = credentials.baseUrl as string;

    for (let i = 0; i < items.length; i++) {
      try {
        const operation = this.getNodeParameter('operation', i) as string;
        let responseData;

        switch (operation) {
          case 'search': {
            const query = this.getNodeParameter('query', i) as string;
            const limit = this.getNodeParameter('limit', i) as number;
            const namespace = this.getNodeParameter('namespace', i) as string;

            const params = new URLSearchParams({
              q: query,
              limit: limit.toString(),
              ...(namespace && { namespace }),
            });

            const response = await this.helpers.request({
              method: 'GET',
              url: `${baseUrl}/api/v1/search?${params}`,
              json: true,
            });

            responseData = response;
            break;
          }

          case 'capture': {
            const text = this.getNodeParameter('text', i) as string;
            const title = this.getNodeParameter('title', i) as string;
            const tags = this.getNodeParameter('tags', i) as string;

            const params = new URLSearchParams({
              text,
              ...(title && { title }),
              ...(tags && { tags }),
            });

            const response = await this.helpers.request({
              method: 'POST',
              url: `${baseUrl}/shortcuts/capture?${params}`,
              json: true,
            });

            responseData = response;
            break;
          }

          case 'stats': {
            const response = await this.helpers.request({
              method: 'GET',
              url: `${baseUrl}/shortcuts/stats`,
              json: true,
            });

            responseData = response;
            break;
          }

          case 'getContent': {
            const contentId = this.getNodeParameter('contentId', i) as string;

            const response = await this.helpers.request({
              method: 'GET',
              url: `${baseUrl}/content/${contentId}`,
              json: true,
            });

            responseData = response;
            break;
          }

          default:
            throw new NodeOperationError(this.getNode(), `Unknown operation: ${operation}`);
        }

        returnData.push({ json: responseData });
      } catch (error) {
        if (this.continueOnFail()) {
          returnData.push({ json: { error: error.message } });
          continue;
        }
        throw error;
      }
    }

    return [returnData];
  }
}
