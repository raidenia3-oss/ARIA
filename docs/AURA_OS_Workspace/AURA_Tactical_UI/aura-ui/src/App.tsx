import { useState } from "react";
import ChatPanel from "./components/ChatPanel";
import LiveBrowser from "./components/LiveBrowser";
import Sidebar from "./components/Sidebar";

export default function App() {
    const [persona, setPersona] = useState("AURA Standard");
    const [provider, setProvider] = useState("Automático");

    return (
        <div className="app split-layout">
            <Sidebar
                persona={persona}
                onPersonaChange={setPersona}
                provider={provider}
                onProviderChange={setProvider}
            />
            <div className="main-area">
                <ChatPanel persona={persona} provider={provider} />
                <LiveBrowser />
            </div>
        </div>
    );
}
