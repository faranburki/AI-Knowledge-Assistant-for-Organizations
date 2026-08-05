let voiceSessionActive = false;
let currentVoiceSessionId = null;
let currentVoiceConversationId = null;
let voiceTimerInterval = null;
let voiceStartTime = null;
let voicePollInterval = null;
let lastMessageCount = 0;

let voiceSignalingWs = null;
let voicePeerConnection = null;
let localMediaStream = null;

async function startVoiceSession() {
  if (voiceSessionActive) return;

  const orgId = API.isPublicUser() 
    ? (API.getSubscribedOrgIds()[0] || null) 
    : (await API.getOrganization().then(o => o.organization_id).catch(() => null));

  if (!orgId) {
    if (typeof showToast === 'function') showToast("Please select an organization first.", "error");
    return;
  }

  try {
    document.getElementById("voiceStatusText").textContent = "Connecting...";
    document.getElementById("btnVoiceConnect").disabled = true;

    const session = await API.createVoiceSession(orgId);
    currentVoiceSessionId = session.session_id;
    currentVoiceConversationId = session.conversation_id;
    voiceSessionActive = true;
    lastMessageCount = 0;

    // Update UI
    document.getElementById("voiceStatusText").textContent = "Connected";
    document.getElementById("btnVoiceConnect").style.display = "none";
    document.getElementById("btnVoiceConnect").disabled = false;
    document.getElementById("btnVoiceDisconnect").style.display = "flex";

    // Show Session ID in UI (Add element if it doesn't exist, or replace status)
    const transcriptBody = document.getElementById("voiceTranscriptBody");
    transcriptBody.innerHTML = `
      <div style="text-align:center; color:var(--text-tertiary); margin-top:10px; font-size:0.9rem;">
        Session Created: <br>
        <span style="font-family: monospace; color: var(--text-primary);">${currentVoiceSessionId}</span>
      </div>
    `;

    // Start Timer
    voiceStartTime = Date.now();
    voiceTimerInterval = setInterval(updateVoiceTimer, 1000);
    updateVoiceTimer();

    // Start WebRTC Signaling
    startWebRTCSignaling(currentVoiceSessionId);

    // Start Polling for Transcripts
    voicePollInterval = setInterval(pollVoiceConversation, 1500);

  } catch (err) {
    console.error("Failed to start voice session:", err);
    document.getElementById("voiceStatusText").textContent = "Error";
    document.getElementById("btnVoiceConnect").disabled = false;
    if (typeof showToast === 'function') showToast(err.message || "Failed to connect", "error");
  }
}

async function endVoiceSession() {
  if (!voiceSessionActive || !currentVoiceSessionId) return;

  try {
    document.getElementById("voiceStatusText").textContent = "Disconnecting...";
    document.getElementById("btnVoiceDisconnect").disabled = true;

    if (voiceSignalingWs) {
      voiceSignalingWs.close();
      voiceSignalingWs = null;
    }
    if (voicePeerConnection) {
      voicePeerConnection.close();
      voicePeerConnection = null;
    }
    if (localMediaStream) {
      localMediaStream.getTracks().forEach(track => track.stop());
      localMediaStream = null;
    }

    await API.endVoiceSession(currentVoiceSessionId);
  } catch (err) {
    console.error("Failed to end session cleanly:", err);
  } finally {
    voiceSessionActive = false;
    currentVoiceSessionId = null;
    currentVoiceConversationId = null;
    
    // Stop Timers
    clearInterval(voiceTimerInterval);
    voiceTimerInterval = null;
    
    if (voicePollInterval) {
      clearInterval(voicePollInterval);
      voicePollInterval = null;
    }
    
    // Reset UI
    document.getElementById("voiceStatusText").textContent = "Disconnected";
    document.getElementById("btnVoiceDisconnect").style.display = "none";
    document.getElementById("btnVoiceDisconnect").disabled = false;
    document.getElementById("btnVoiceConnect").style.display = "flex";
    
    const transcriptBody = document.getElementById("voiceTranscriptBody");
    transcriptBody.innerHTML = `
      <div style="text-align:center; color:var(--text-tertiary); margin-top:40px; font-size:0.9rem;">
        Session ended.
      </div>
    `;
  }
}

function updateVoiceTimer() {
  if (!voiceStartTime) return;
  const diff = Math.floor((Date.now() - voiceStartTime) / 1000);
  const m = Math.floor(diff / 60).toString().padStart(2, '0');
  const s = (diff % 60).toString().padStart(2, '0');
  const timerEl = document.getElementById("voiceDuration");
  if (timerEl) {
    timerEl.textContent = `${m}:${s}`;
  }
}

let lastHistoryHash = "";

async function pollVoiceConversation() {
  if (!voiceSessionActive || !currentVoiceConversationId) return;
  
  try {
    const history = await API.getConversationHistory(currentVoiceConversationId);
    if (history && history.length > 0) {
      const currentHash = JSON.stringify(history);
      if (currentHash !== lastHistoryHash) {
        lastHistoryHash = currentHash;
        renderVoiceTranscript(history);
      }
    }
  } catch (e) {
    // Ignore network errors or 404s if conversation is empty
  }
}

function renderVoiceTranscript(history) {
  const container = document.getElementById("voiceTranscriptBody");
  // Keep the session ID header if it exists
  const headerHtml = container.innerHTML.includes("Session Created") ? container.innerHTML.split('</div>')[0] + '</div>' : '';
  
  let html = headerHtml;
  
  for (const msg of history) {
    // User Question Bubble
    html += `
      <div class="transcript-message user">
        <span class="transcript-author">You</span>
        <div class="transcript-bubble">${escapeHTML(msg.question)}</div>
      </div>
    `;
    
    // AI Answer Bubble
    html += `
      <div class="transcript-message ai">
        <span class="transcript-author">AI Agent</span>
        <div class="transcript-bubble">${escapeHTML(msg.answer)}</div>
      </div>
    `;
  }
  
  container.innerHTML = html;
  container.scrollTop = container.scrollHeight;
}

function escapeHTML(str) {
  if (!str) return '';
  return String(str).replace(/[&<>'"]/g, 
    tag => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      "'": '&#39;',
      '"': '&quot;'
    }[tag])
  );
}

async function startWebRTCSignaling(sessionId) {
  const token = API._token();
  if (!token) return;

  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Use API_BASE if defined, otherwise derive from host
  let host = window.location.host;
  if (typeof API_BASE !== 'undefined' && API_BASE) {
    const url = new URL(API_BASE);
    host = url.host;
  }
  
  const wsUrl = `${protocol}//${host}/voice-sessions/${sessionId}/webrtc?token=${token}`;
  
  voiceSignalingWs = new WebSocket(wsUrl);
  
  voiceSignalingWs.onopen = async () => {
    console.log("Voice Signaling WebSocket Connected");
    
    // Create PeerConnection
    voicePeerConnection = new RTCPeerConnection({
      iceServers: [{ urls: 'stun:stun.l.google.com:19302' }]
    });

    // Request Microphone Access
    try {
      localMediaStream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });

      // Set up local microphone volume analysis for orb animation
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const analyser = audioContext.createAnalyser();
      const source = audioContext.createMediaStreamSource(localMediaStream);
      source.connect(analyser);
      analyser.fftSize = 256;
      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);
      
      function checkMicVolume() {
        if (!voiceSessionActive) return;
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const average = sum / bufferLength;
        
        const orb = document.getElementById("voiceOrb");
        const statusEl = document.getElementById("voiceStatusText");
        
        if (orb) {
          // Increase threshold to 40 to completely ignore background noise/static
          if (average > 40 && statusEl && statusEl.textContent === "Connected (WebRTC Ready)") {
            orb.classList.add("user-speaking");
            orb.style.transition = "none";
            orb.style.transform = `scale(${1 + (average / 255) * 0.4})`;
          } else {
            orb.classList.remove("user-speaking");
            if (!orb.classList.contains("ai-speaking")) {
              orb.style.transition = "all 0.3s ease";
              orb.style.transform = "scale(1)";
            }
          }
        }
        requestAnimationFrame(checkMicVolume);
      }
      checkMicVolume();
      
      // The old onplay/onpause events are removed because they don't work with continuous silence WebRTC streams.
      // We will instead dynamically analyze the remote track volume in ontrack.
      
      // Add local audio track to PC
      localMediaStream.getTracks().forEach(track => {
        voicePeerConnection.addTrack(track, localMediaStream);
      });
      console.log("Microphone access granted and track added to WebRTC.");
    } catch (err) {
      console.error("Failed to access microphone:", err);
      document.getElementById("voiceStatusText").textContent = "Mic Error";
      return;
    }
    
    // Receive TTS audio from backend
    voicePeerConnection.ontrack = event => {
      console.log("Received remote track:", event.track.kind);
      if (event.track.kind === 'audio') {
        let audioEl = document.getElementById("voiceAudioOutput");
        if (!audioEl) {
          audioEl = document.createElement("audio");
          audioEl.id = "voiceAudioOutput";
          audioEl.autoplay = true;
          document.body.appendChild(audioEl);
        }
        let streamToAnalyze;
        // event.streams[0] might be empty if the backend didn't construct a stream properly
        if (event.streams && event.streams[0]) {
          streamToAnalyze = event.streams[0];
          audioEl.srcObject = streamToAnalyze;
        } else {
          streamToAnalyze = new MediaStream([event.track]);
          audioEl.srcObject = streamToAnalyze;
        }
        
        // Analyze remote audio volume to sync AI animations perfectly
        const remoteAudioContext = new (window.AudioContext || window.webkitAudioContext)();
        const remoteAnalyser = remoteAudioContext.createAnalyser();
        const remoteSource = remoteAudioContext.createMediaStreamSource(streamToAnalyze);
        remoteSource.connect(remoteAnalyser);
        remoteAnalyser.fftSize = 256;
        const remoteBufferLength = remoteAnalyser.frequencyBinCount;
        const remoteDataArray = new Uint8Array(remoteBufferLength);
        
        function checkRemoteVolume() {
          if (!voiceSessionActive) return;
          remoteAnalyser.getByteFrequencyData(remoteDataArray);
          let sum = 0;
          for (let i = 0; i < remoteBufferLength; i++) {
            sum += remoteDataArray[i];
          }
          const average = sum / remoteBufferLength;
          const orb = document.getElementById("voiceOrb");
          if (orb) {
            if (average > 10) {
              orb.classList.add("ai-speaking");
              orb.style.transition = "none";
              orb.style.animation = "none";
              orb.style.transform = `scale(${1 + (average / 255) * 0.4})`;
            } else {
              orb.classList.remove("ai-speaking");
              if (!orb.classList.contains("user-speaking")) {
                orb.style.transition = "all 0.3s ease";
                orb.style.transform = "scale(1)";
              }
            }
          }
          requestAnimationFrame(checkRemoteVolume);
        }
        checkRemoteVolume();
      }
    };
    
    // Send ICE candidates to backend
    voicePeerConnection.onicecandidate = event => {
      if (event.candidate && voiceSignalingWs.readyState === WebSocket.OPEN) {
        voiceSignalingWs.send(JSON.stringify({
          type: 'candidate',
          candidate: event.candidate.toJSON()
        }));
      }
    };
    
    // Listen for state changes
    voicePeerConnection.oniceconnectionstatechange = () => {
      console.log("ICE Connection State:", voicePeerConnection.iceConnectionState);
      if (voicePeerConnection.iceConnectionState === "connected") {
        document.getElementById("voiceStatusText").textContent = "Connected (WebRTC Ready)";
      } else if (voicePeerConnection.iceConnectionState === "disconnected" || voicePeerConnection.iceConnectionState === "failed") {
        document.getElementById("voiceStatusText").textContent = "WebRTC Failed";
      }
    };
    
    // Create and send offer (We set offerToReceiveAudio to true since we aren't adding tracks yet)
    try {
      const offer = await voicePeerConnection.createOffer({ offerToReceiveAudio: true });
      await voicePeerConnection.setLocalDescription(offer);
      
      voiceSignalingWs.send(JSON.stringify({
        type: offer.type,
        sdp: offer.sdp
      }));
    } catch (e) {
      console.error("Failed to create WebRTC offer:", e);
    }
  };
  
  voiceSignalingWs.onmessage = async (event) => {
    const message = JSON.parse(event.data);
    
    if (message.type === 'answer') {
      console.log("Received WebRTC Answer");
      await voicePeerConnection.setRemoteDescription(new RTCSessionDescription(message));
    } else if (message.type === 'candidate') {
      console.log("Received remote ICE candidate");
      await voicePeerConnection.addIceCandidate(new RTCIceCandidate(message.candidate));
    }
  };
  
  voiceSignalingWs.onerror = (e) => {
    console.error("Voice Signaling WebSocket Error", e);
  };
  
  voiceSignalingWs.onclose = () => {
    console.log("Voice Signaling WebSocket Closed");
  };
}

// Bind events once DOM is loaded
document.addEventListener("DOMContentLoaded", () => {
  const btnConnect = document.getElementById("btnVoiceConnect");
  const btnDisconnect = document.getElementById("btnVoiceDisconnect");

  if (btnConnect) {
    btnConnect.addEventListener("click", startVoiceSession);
  }
  if (btnDisconnect) {
    btnDisconnect.addEventListener("click", endVoiceSession);
  }
});
