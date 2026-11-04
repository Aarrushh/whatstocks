import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import "./index.css"
import { App, NoData } from "./App"
import { loadModel } from "./lib/data"

const root = createRoot(document.getElementById("root")!)

loadModel().then(
  (model) =>
    root.render(
      <StrictMode>{model ? <App model={model} /> : <NoData />}</StrictMode>,
    ),
  (err: unknown) => root.render(<NoData error={String(err)} />),
)
