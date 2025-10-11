import { useState, useCallback, useEffect } from "react";
import { usePipecatClient, useRTVIClientEvent } from "@pipecat-ai/client-react";
import { RTVIEvent } from "@pipecat-ai/client-js";
import "./ASLImageDisplay.css";

interface ASLImageData {
  imageData: string; 
  timestamp: number;
  word?: string; 
}

export function ASLImageDisplay() {
  const [currentImage, setCurrentImage] = useState<ASLImageData | null>(null);
  const [imageHistory, setImageHistory] = useState<ASLImageData[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const client = usePipecatClient();

  // Handle image data from server messages
  const handleImageMessage = useCallback((message: { type: string; image?: string; format?: string; timestamp?: number; word?: string }) => {
    // Validate message structure
    if (!message || typeof message !== 'object') {
      return;
    }
    
    // Check if this is an ASL image message
    if (message && message.type === "asl_image" && message.image) {
      try {
        // Validate base64 data
        if (typeof message.image !== 'string' || message.image.length === 0) {
          console.error("Invalid base64 image data");
          return;
        }
        
        // Create data URL from base64 image
        const format = message.format?.toLowerCase() || 'png';
        const imageData = `data:image/${format};base64,${message.image}`;
        
        const newImageData: ASLImageData = {
          imageData,
          timestamp: message.timestamp || Date.now(),
          word: message.word || undefined
        };
        
        setCurrentImage(newImageData);
        setImageHistory(prev => {
          const newHistory = [...prev.slice(-4), newImageData]; // Keep last 5 images
          return newHistory;
        });
      } catch (error) {
        console.error("Error processing image message:", error);
        // Set a fallback state
        setCurrentImage(null);
      }
    }
  }, []);

  // Listen for server messages containing image data
  useRTVIClientEvent(
    RTVIEvent.ServerMessage,
    useCallback(
      (message: { type: string; image?: string; format?: string; timestamp?: number; word?: string }) => {
        console.log("RTVI ServerMessage event received:", message);
        handleImageMessage(message);
      },
      [handleImageMessage]
    )
  );


  // Listen for connection state changes
  useEffect(() => {
    if (!client) {
      return;
    }

    const handleConnectionChange = () => {
      const connected = client.connected;
      setIsConnected(connected);
    };

    // Check initial state
    handleConnectionChange();

    // Listen for transport state changes
    const handleTransportStateChange = () => {
      handleConnectionChange();
    };

    client.addListener('transportStateChanged', handleTransportStateChange);
    
    return () => {
      client.removeListener('transportStateChanged', handleTransportStateChange);
    };
  }, [client]);

  if (!isConnected && !currentImage) {
    return (
      <div className="asl-image-display">
        <div className="asl-placeholder">
          <p>Connect to see ASL hand signs</p>
        </div>
      </div>
    );
  }


  return (
    <div className="asl-image-display">
      <div className="current-image-container">
        {currentImage ? (
          <div className="current-image">
            <img 
              src={currentImage.imageData} 
              alt="ASL Hand Sign"
              className="hand-sign-image"
            />
            {currentImage.word && (
              <div className="word-label">{currentImage.word}</div>
            )}
          </div>
        ) : (
          <div className="asl-placeholder">
            <p>Waiting for hand signs...</p>
          </div>
        )}
      </div>
      
      {imageHistory.length > 0 && (
        <div className="image-history">
          <h4>Recent Signs</h4>
          <div className="history-images">
            {imageHistory.slice(-4).map((img, index) => (
              <div key={img.timestamp} className="history-image">
                <img 
                  src={img.imageData} 
                  alt={`Previous sign ${index + 1}`}
                  className="history-hand-sign"
                />
                {img.word && (
                  <div className="history-word">{img.word}</div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
