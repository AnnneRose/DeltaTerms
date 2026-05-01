import { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router";
import { ExternalLink, MessageSquare, RefreshCw } from "lucide-react";

type Service = {
  id: string;
  name: string;
  url: string;
  lastAccepted: string;
  hasChanges: boolean;
};

type TosHistoryApiItem = {
  id: number;
  chatbot_name: string;
  website_url: string;
  delta?: string | null;
};

function mapToServices(raw: TosHistoryApiItem[]): Service[] {
  return raw.map((item) => ({
    id: String(item.id),
    name: item.chatbot_name,
    url: item.website_url,
    lastAccepted: "N/A",
    hasChanges: !!item.delta,
  }));
}

export function Dashboard() {
  const navigate = useNavigate();
  const location = useLocation();
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    async function loadServices() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/tos-history", {
          credentials: "include",
          method: "GET",
          signal,
        });
        if (signal.aborted) {
          return;
        }
        if (!response.ok) {
          if (response.status === 401) {
            setError("Session expired. Please sign in again.");
            return;
          }
          throw new Error(`Request failed (${response.status})`);
        }
        const rawData: TosHistoryApiItem[] = await response.json();
        if (signal.aborted) {
          return;
        }
        setServices(mapToServices(rawData));
      } catch (err) {
        if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load services");
        setServices([]);
      } finally {
        if (!signal.aborted) {
          setLoading(false);
        }
      }
    }

    void loadServices();
    return () => controller.abort();
  }, [location.key]);

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">Your Services</h1>
        <p className="text-gray-600">Track and review Terms of Service changes across your services</p>
      </div>

      {loading && (
        <div className="text-center py-12 text-gray-500" aria-live="polite">
          Loading your services…
        </div>
      )}

      {!loading && error && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm" role="alert">
          {error}
        </div>
      )}

      {!loading && !error && services.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {services.map((service) => (
            <div
              key={service.id}
              className="bg-white border border-gray-200 rounded-lg p-6 hover:shadow-md transition-shadow"
            >
              <div className="flex items-start justify-between mb-4">
                <h3 className="text-xl font-semibold text-gray-900">{service.name}</h3>
                {service.hasChanges && (
                  <span className="bg-orange-100 text-orange-700 text-xs px-2 py-1 rounded-full">
                    Changes
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2 text-sm text-blue-600 mb-4 hover:underline">
                <ExternalLink size={16} />
                <a href={service.url} target="_blank" rel="noopener noreferrer" className="truncate">
                  {service.url}
                </a>
              </div>

              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => navigate(`/chat/${service.id}`)}
                  className="flex-1 flex items-center justify-center gap-2 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
                >
                  <MessageSquare size={18} />
                  <span>Review & Chat</span>
                </button>
                <button
                  type="button"
                  onClick={() =>
                    navigate("/upload", {
                      state: { serviceName: service.name, url: service.url },
                    })
                  }
                  className="flex items-center justify-center gap-2 border border-gray-300 text-gray-700 py-2 px-4 rounded-md hover:bg-gray-50 transition-colors"
                  title="Upload an updated version"
                >
                  <RefreshCw size={18} />
                  <span>Update</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && services.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No services tracked yet</p>
          <button
            type="button"
            onClick={() => navigate("/upload")}
            className="bg-blue-600 text-white py-2 px-6 rounded-md hover:bg-blue-700 transition-colors"
          >
            Add Your First ToS
          </button>
        </div>
      )}
    </div>
  );
}
