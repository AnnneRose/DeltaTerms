import { createBrowserRouter } from "react-router-dom";
import { Login } from "./components/Login";
import { Dashboard } from "./components/Dashboard";
import { Upload } from "./components/Upload";
import { Chat } from "./components/Chat";
import { Layout } from "./components/Layout";

export const router = createBrowserRouter([
  {
    path: "/",
    Component: Layout,
    children: [
      { index: true, Component: Login },
      { path: "dashboard", Component: Dashboard },
      { path: "upload", Component: Upload },
      { path: "chat/:serviceId", Component: Chat },
    ],
  },
]);
