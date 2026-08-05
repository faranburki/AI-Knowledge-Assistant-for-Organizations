import { request } from './baseApi.js';

export const AuthApi = {
  login(email, password) {
    return request('POST', '/auth/login', { email, password });
  },
  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = 'index.html';
  }
};
