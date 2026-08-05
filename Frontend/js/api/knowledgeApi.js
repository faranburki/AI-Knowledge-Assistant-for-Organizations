import { request, upload } from './baseApi.js';

export const KnowledgeApi = {
  listDocuments(limit = 50, skip = 0) {
    return request('GET', `/documents/list?limit=${limit}&skip=${skip}`);
  },
  uploadDocument(file, title, description, tags, status = 'private') {
    const fd = new FormData();
    fd.append('file', file);
    if (title) fd.append('title', title);
    if (description) fd.append('description', description);
    if (tags) fd.append('tags', tags);
    if (status) fd.append('status', status);
    return upload('/documents/upload', fd);
  },
  deleteDocument(docId) {
    return request('DELETE', `/documents/${docId}`);
  }
};
