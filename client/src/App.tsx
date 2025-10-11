import { useRef } from "react";
import { PipecatProvider } from "./providers/PipecatProvider";
import { ConnectButton } from "./components/ConnectButton";
import { StatusDisplay } from "./components/StatusDisplay";
import { DebugDisplay, type DebugDisplayRef } from "./components/DebugDisplay";
import { ASLImageDisplay } from "./components/ASLImageDisplay";
import "./App.css";

function AppContent() {
  const debugDisplayRef = useRef<DebugDisplayRef>(null);

  const handleLog = (message: string) => {
    debugDisplayRef.current?.log(message);
  };

  return (
    <div className="app">
      <div className="status-bar">
        <StatusDisplay />
        <ConnectButton onLog={handleLog} />
      </div>

      <div className="main-content">
        <ASLImageDisplay />
      </div>

      <DebugDisplay ref={debugDisplayRef} />
    </div>
  );
}

function App() {
  return (
    <PipecatProvider>
      <AppContent />
    </PipecatProvider>
  );
}

export default App;
