(function() {
    // Prevent multiple instances
    if (window.WebVoxWidgetInitialized) return;
    window.WebVoxWidgetInitialized = true;
  
    // === CONFIGURATION ===
    const chatbotURL = "http://localhost:3000"; // React app running locally
    const width = 380;  // iframe width
    const height = 520; // iframe height
    const position = "bottom-right"; // bottom-left, bottom-right, top-left, top-right
  
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
        background-color: #0052cc;
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
      }
    `;
    document.head.appendChild(style);
  
    // === CREATE ELEMENTS ===
    const launcher = document.createElement("div");
    launcher.id = "webvox-launcher";
    launcher.innerHTML = "💬"; // chat icon
  
    const iframeContainer = document.createElement("div");
    iframeContainer.id = "webvox-iframe-container";
  
    const closeButton = document.createElement("button");
    closeButton.id = "webvox-close";
    closeButton.textContent = "×";
  
    const iframe = document.createElement("iframe");
    iframe.id = "webvox-iframe";
    iframe.src = chatbotURL;
    iframe.allow = "microphone; camera"; // if voice input is used
  
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
  