import { Outlet, useNavigate, useLocation } from "react-router";
import { FileText, Upload, LogOut } from "lucide-react";

export function Layout() {
  const navigate = useNavigate();
  const location = useLocation();
  const isLoggedIn = location.pathname !== "/";

  const handleLogout = async () => {
    try {
      await fetch("http://localhost:5000/api/logout", {
        method: "POST",
        credentials: "include",
      });
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      navigate("/");
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {isLoggedIn && (
        <header className="bg-white border-b border-gray-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <div className="flex items-center gap-8">
                <h1 className="font-semibold text-gray-900">ToS Tracker</h1>
                <nav className="flex gap-4">
                  <button
                    onClick={() => navigate("/dashboard")}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors ${
                      location.pathname === "/dashboard"
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    <FileText size={18} />
                    <span>Dashboard</span>
                  </button>
                  <button
                    onClick={() => navigate("/upload")}
                    className={`flex items-center gap-2 px-3 py-2 rounded-md transition-colors ${
                      location.pathname === "/upload"
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    <Upload size={18} />
                    <span>Add ToS</span>
                  </button>
                </nav>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:bg-gray-100 rounded-md transition-colors"
              >
                <LogOut size={18} />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </header>
      )}
      <main className={isLoggedIn ? "max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8" : ""}>
        <Outlet />
      </main>
    </div>
  );
}
