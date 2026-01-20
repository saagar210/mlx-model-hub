import {
  ICredentialType,
  INodeProperties,
} from 'n8n-workflow';

export class KasApi implements ICredentialType {
  name = 'kasApi';
  displayName = 'KAS API';
  documentationUrl = 'https://github.com/saagar210/knowledge-activation-system';
  properties: INodeProperties[] = [
    {
      displayName: 'Base URL',
      name: 'baseUrl',
      type: 'string',
      default: 'http://localhost:8000',
      description: 'The base URL of the KAS API',
    },
    {
      displayName: 'API Key',
      name: 'apiKey',
      type: 'string',
      typeOptions: {
        password: true,
      },
      default: '',
      description: 'API key for authentication (optional)',
    },
  ];
}
