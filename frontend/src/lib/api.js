export const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  async _post(endpoint, data) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _get(endpoint) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _delete(endpoint) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'DELETE',
      headers: {
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _patch(endpoint, data) {
    const res = await fetch(`${API_URL}${endpoint}`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${localStorage.getItem('token')}`,
      },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const errorData = await res.json();
      throw new Error(errorData.detail || `API error: ${res.statusText}`);
    }

    return res.json();
  }

  async _get_stream(endpoint, params = {}, onMessage) {
    if (typeof params === 'function' && !onMessage) {
      onMessage = params;
      params = {};
    }

    const searchParams = new URLSearchParams({
      ...params,
      token: localStorage.getItem('token'),
    });

    const eventSource = new EventSource(
      `${API_URL}${endpoint}?${searchParams.toString()}`
    );

    return new Promise((resolve, reject) => {
      eventSource.onmessage = (event) => {
        onMessage?.(event.data);
      };

      eventSource.onerror = (error) => {
        eventSource.close();
        console.warning(error);
        resolve();
      };

      eventSource.addEventListener('complete', () => {
        eventSource.close();
        resolve();
      });
    });
  }

  async createAccount(username, email) {
    const res = await this._post('/api/auth/create', { username, email });
    localStorage.setItem('token', res.token);
    localStorage.setItem('username', res.user.username);
    return res.user;
  }

  async getCurrentUser() {
    return this._get('/api/auth/me');
  }

  async getTeams() {
    return this._get('/api/teams');
  }

  async getChats() {
    return this._get('/api/chats');
  }

  async createChat(chat) {
    return this._post('/api/chats', chat);
  }

  async getChat(chatId) {
    return this._get(`/api/chats/${chatId}`);
  }

  async updateChat(chatId, chat) {
    return this._patch(`/api/chats/${chatId}`, chat);
  }

  async getTeamProjects(teamId) {
    return this._get(`/api/teams/${teamId}/projects`);
  }

  async getProject(teamId, projectId) {
    return this._get(`/api/teams/${teamId}/projects/${projectId}`);
  }

  async getProjectFile(teamId, projectId, filePath) {
    return this._get(
      `/api/teams/${teamId}/projects/${projectId}/file/${filePath}`
    );
  }

  async getProjectGitLog(teamId, projectId) {
    return this._get(`/api/teams/${teamId}/projects/${projectId}/git-log`);
  }

  async getStackPacks() {
    return this._get('/api/stacks');
  }

  async deleteChat(chatId) {
    return this._delete(`/api/chats/${chatId}`);
  }

  async getImageUploadUrl(contentType) {
    return this._post(`/api/uploads/image-upload-url`, {
      content_type: contentType,
    });
  }

  async updateProject(teamId, projectId, projectData) {
    return this._patch(
      `/api/teams/${teamId}/projects/${projectId}`,
      projectData
    );
  }

  async getProjectChats(teamId, projectId) {
    return this._get(`/api/teams/${teamId}/projects/${projectId}/chats`);
  }

  async deleteProject(teamId, projectId) {
    return this._delete(`/api/teams/${teamId}/projects/${projectId}`);
  }

  async restartProject(teamId, projectId) {
    return this._post(`/api/teams/${teamId}/projects/${projectId}/restart`);
  }

  async generateTeamInvite(teamId) {
    return this._post(`/api/teams/${teamId}/invites`);
  }

  async joinTeamWithInvite(inviteCode) {
    return this._post(`/api/teams/join/${inviteCode}`);
  }

  async updateUser(updates) {
    const response = await this._patch('/api/auth/me', updates);
    return response;
  }

  async updateTeam(teamId, teamData) {
    return this._patch(`/api/teams/${teamId}`, teamData);
  }

  async getTeamMembers(teamId) {
    return this._get(`/api/teams/${teamId}/members`);
  }

  async updateTeamMember(teamId, userId, memberData) {
    return this._patch(`/api/teams/${teamId}/members/${userId}`, memberData);
  }

  async removeTeamMember(teamId, userId) {
    return this._delete(`/api/teams/${teamId}/members/${userId}`);
  }

  async zipProject(teamId, projectId) {
    return this._post(`/api/teams/${teamId}/projects/${projectId}/zip`);
  }

  async deployCreateGithub(teamId, projectId, deployData, onMessage) {
    return this._get_stream(
      `/api/teams/${teamId}/projects/${projectId}/deploy-create/github`,
      deployData,
      onMessage
    );
  }

  async deployStatusGithub(teamId, projectId) {
    return this._get(
      `/api/teams/${teamId}/projects/${projectId}/deploy-status/github`
    );
  }

  async deployPushGithub(teamId, projectId) {
    return this._post(
      `/api/teams/${teamId}/projects/${projectId}/deploy-push/github`
    );
  }

  async getPublicChat(shareId) {
    return this._get(`/api/chats/public/${shareId}`);
  }

  async getPublicChatPreviewUrl(shareId) {
    return this._get(`/api/chats/public/${shareId}/preview-url`);
  }

  async shareChat(chatId) {
    return this._post(`/api/chats/${chatId}/share`);
  }

  async unshareChat(chatId) {
    return this._post(`/api/chats/${chatId}/unshare`);
  }

  async emailLogin(token) {
    const res = await this._get(`/api/auth/email-login/${token}`);
    localStorage.setItem('token', res.token);
    localStorage.setItem('username', res.user.username);
    return res.user;
  }

  async getProjectEnvVars(teamId, projectId) {
    const response = await this._get(
      `/api/teams/${teamId}/projects/${projectId}/env-vars`
    );
    return response;
  }

  async updateProjectEnvVars(teamId, projectId, data) {
    const response = await this._post(
      `/api/teams/${teamId}/projects/${projectId}/env-vars`,
      data
    );
    return response;
  }
}

export async function uploadImage(imageData, contentType) {
  const { upload_url, url } = await api.getImageUploadUrl(contentType);

  let blob;
  if (imageData instanceof Blob) {
    blob = imageData;
  } else {
    const response = await fetch(imageData);
    blob = await response.blob();
  }

  await fetch(upload_url, {
    method: 'PUT',
    body: blob,
    headers: {
      'Content-Type': contentType || blob.type,
    },
  });

  return url;
}

// Export singleton instance
export const api = new ApiClient();
