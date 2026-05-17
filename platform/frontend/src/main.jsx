import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { purgeLegacy } from "./auth/flow";
import "./index.css";

// One-time cleanup of pre-namespacing keys that could leak between accounts.
purgeLegacy();

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
