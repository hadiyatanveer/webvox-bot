export async function sendMessageToBot(input) {
    const apiUrl = "http://localhost:8000";
    const response = await fetch(`${apiUrl}/api/v1/chat`, { 
      method: "POST",
      headers: {  "Content-Type": "application/json"  },
      body: JSON.stringify({  message: input, session_id: "default" })
    });
  
    if (!response.ok) {
      throw new Error(`Server error: ${response.status}`);
    }
  
    const data = await response.json();
    console.log("Bot reply:", data.response);
    return data.response; 
}
