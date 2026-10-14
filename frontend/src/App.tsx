import { backendStatusLabel, useBackendStatus } from "./hooks/useBackendStatus.ts"

function App() {
  const status = useBackendStatus()

  return (
    <main className="shell">
      <p className="eyebrow">AgentGuard</p>
      <h1>Jev Decision Explorer</h1>
      <p className="description">
        Explore Jev's typed decision APIs, inspect JSON requests and responses, and
        understand how structured decisions can drive application logic.
      </p>
      <p className={`status status-${status}`} role="status">
        {backendStatusLabel(status)}
      </p>
    </main>
  )
}

export default App
