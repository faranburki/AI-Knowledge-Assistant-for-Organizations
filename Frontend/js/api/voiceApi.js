import { request } from './baseApi.js';

export const VoiceApi = {
  createSession(organization_id, conversation_id = null) {
    const payload = {
      organization_id,
      conversation_id,
      session_type: "push_to_talk",
      agent_id: null
    };
    return request('POST', '/voice-sessions/', payload);
  }
};
