import { useRef } from "react";
import {
  usePipecatClient,
  usePipecatClientTransportState,
} from "@pipecat-ai/client-react";

interface ConnectButtonProps {
  onLog?: (message: string) => void;
}

export function ConnectButton({ onLog }: ConnectButtonProps) {
  const client = usePipecatClient();
  const transportState = usePipecatClientTransportState();
  const isConnected = ["connected", "ready"].includes(transportState);
  const startTimeRef = useRef<number | null>(null);

  const handleClick = async () => {
    if (!client) {
      console.error("Pipecat client is not initialized");
      onLog?.("Error: Pipecat client is not initialized");
      return;
    }

    try {
      if (isConnected) {
        onLog?.("Disconnecting...");
        await client.disconnect();
      } else {
        startTimeRef.current = Date.now();
        onLog?.("Initializing devices...");
        
        await client.initDevices();
        
        onLog?.("Connecting to bot...");
        await client.startBotAndConnect({
          endpoint: "/connect",
        });

        if (startTimeRef.current) {
          const timeTaken = Date.now() - startTimeRef.current;
          onLog?.(`Connection complete, timeTaken: ${timeTaken}ms`);
        }
      }
    } catch (error) {
      const errorMessage = `Error ${isConnected ? 'disconnecting' : 'connecting'}: ${(error as Error).message}`;
      console.error(errorMessage);
      onLog?.(errorMessage);
      
      // Clean up if there's an error during connection
      if (!isConnected && client) {
        try {
          await client.disconnect();
        } catch (disconnectError) {
          onLog?.(`Error during cleanup: ${disconnectError}`);
        }
      }
    }
  };

  return (
    <div className="controls">
      <button
        className={isConnected ? "disconnect-btn" : "connect-btn"}
        onClick={handleClick}
        disabled={
          !client || ["connecting", "disconnecting"].includes(transportState)
        }
      >
        {isConnected ? "Disconnect" : "Connect"}
      </button>
    </div>
  );
}
