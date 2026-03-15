(function () {
  // Prevent multiple instances
  if (window.WebVoxWidgetInitialized) return;
  window.WebVoxWidgetInitialized = true;

  // === CONFIGURATION ===
  if (!window.WebVoxConfig || Object.keys(window.WebVoxConfig).length === 0) {
    window.WebVoxConfig = {
      url: "http://localhost:3000",
      primaryColor: "#0052cc",     
      agentColor: "#e6f0ff",      
      botName: "WebVox Bot",
      mode: "widget"
    };
  }
  const config = window.WebVoxConfig;
  const chatbotURL = config.url || "http://localhost:3000";
  const primaryColor = config.primaryColor || "#0052cc";
  const botName = config.botName || "WebVox Bot";
  const mode = config.mode || "widget";

  const width = config.width || 380;
  const height = config.height || 520;
  const position = config.position || "bottom-right";

  // === STYLES ===
  const style = document.createElement("style");
  style.innerHTML = `
      #webvox-launcher {
        position: fixed;
        ${position.includes("bottom") ? "bottom: 20px;" : "top: 20px;"}
        ${position.includes("right") ? "right: 20px;" : "left: 20px;"}
        width: 60px;
        height: 60px;
        border-radius: 50%;
        background-color: ${primaryColor};
        color: white;
        font-size: 30px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 2147483000;
        transition: all 0.3s ease;
      }
      #webvox-launcher:hover { transform: scale(1.05); }
  
      #webvox-iframe-container {
        position: fixed;
        ${position.includes("bottom") ? `bottom: 90px;` : `top: 90px;`}
        ${position.includes("right") ? `right: 20px;` : `left: 20px;`}
        width: ${width}px;
        height: ${height}px;
        border-radius: 12px;
        overflow: hidden;
        box-shadow: 0 6px 20px rgba(0,0,0,0.35);
        display: none;
        flex-direction: column;
        z-index: 2147483000;
      }
  
      #webvox-iframe {
        width: 100%;
        height: 100%;
        border: none;
      }
  
      #webvox-close {
        position: absolute;
        top: 8px;
        right: 8px;
        background: rgba(0,0,0,0.6);
        color: white;
        border: none;
        border-radius: 50%;
        width: 24px;
        height: 24px;
        font-size: 16px;
        cursor: pointer;
        z-index: 10;
        display: none; /* Hide default close, we use the header close */
      }
    `;
  document.head.appendChild(style);

  // === CREATE ELEMENTS ===
  const launcher = document.createElement("div");
  launcher.id = "webvox-launcher";

  // Detection for Image vs Icon
  const launcherIcon = config.launcherIcon || "💬";
  if (launcherIcon.match(/\.(jpeg|jpg|gif|png|svg)$/) || launcherIcon.startsWith('http')) {
    launcher.innerHTML = `<img src="${launcherIcon}" style="width: 100%; height: 100%; border-radius: 50%; object-fit: cover;" />`;
    launcher.style.padding = "0"; // Remove padding for full-bleed images
    launcher.style.overflow = "hidden";
  } else {
    launcher.innerHTML = launcherIcon;
  }

  const iframeContainer = document.createElement("div");
  iframeContainer.id = "webvox-iframe-container";

  const closeButton = document.createElement("button");
  closeButton.id = "webvox-close";
  closeButton.textContent = "×";

  const iframe = document.createElement("iframe");
  iframe.id = "webvox-iframe";

  // Build Iframe URL with params
  const url = new URL(chatbotURL);
  url.searchParams.set('mode', mode);
  url.searchParams.set('primaryColor', primaryColor);
  if (config.botName) url.searchParams.set('botName', config.botName);
  if (config.statusColor) url.searchParams.set('statusColor', config.statusColor);
  if (config.agentColor) url.searchParams.set('agentColor', config.agentColor);
  if (config.micColor) url.searchParams.set('micColor', config.micColor);
  if (config.bgColor) url.searchParams.set('bgColor', config.bgColor);
  if (config.textColor) url.searchParams.set('textColor', config.textColor);
  if (config.iconUrl) url.searchParams.set('iconUrl', config.iconUrl);

  iframe.src = url.toString();
  iframe.allow = "microphone; camera";

  // Pass configuration to iframe via postMessage for real-time CSS updates (optional)
  iframe.onload = () => {
    iframe.contentWindow.postMessage({ type: 'SET_CONFIG', config }, "*");
  };

  iframeContainer.appendChild(closeButton);
  iframeContainer.appendChild(iframe);

  document.body.appendChild(launcher);
  document.body.appendChild(iframeContainer);

  // === EVENT HANDLERS ===
  launcher.addEventListener("click", () => {
    iframeContainer.style.display = iframeContainer.style.display === "flex" ? "none" : "flex";
  });

  closeButton.addEventListener("click", () => {
    iframeContainer.style.display = "none";
  });

  // Optional: postMessage communication (if you want future interaction)
  window.addEventListener("message", (event) => {
    // Only allow messages from your React app origin
    if (!event.origin.includes("localhost:3000")) return;

    if (event.data === "close-widget") {
      iframeContainer.style.display = "none";
    }
  });

})();
