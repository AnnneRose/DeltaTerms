import { useNavigate } from "react-router";
import { ExternalLink, MessageSquare, Calendar } from "lucide-react";

type Service = {
  id: string;
  name: string;
  url: string;
  lastAccepted: string;
  hasChanges: boolean;
};
let mockServices: Service[];
try {
  const rawData = await fetch("http://localhost:5000/api/tos-history", {
    credentials: "include",
    method: "GET",
  }).then((res) => res.json());
  console.log("Fetched services:", rawData);
  mockServices = rawData.map((item: any) => ({
    id: String(item.id),
    name: item.chatbot_name,
    url: item.website_url,
    lastAccepted: "N/A", // you don't have this in backend yet
    hasChanges: !!item.delta, // assume delta means changes exist
  }));
} catch (error) {
  console.log(error);
  mockServices =[];
}


export function Dashboard() {
  const navigate = useNavigate();

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">Your Services</h1>
        <p className="text-gray-600">Track and review Terms of Service changes across your services</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {mockServices.map((service) => (
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

            {/* <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
              <Calendar size={16} />
              <span>Accepted: {service.lastAccepted}</span>
            </div> */}

            <div className="flex items-center gap-2 text-sm text-blue-600 mb-4 hover:underline">
              <ExternalLink size={16} />
              <a href={service.url} target="_blank" rel="noopener noreferrer" className="truncate">
                {service.url}
              </a>
            </div>

            <button
              onClick={() => navigate(`/chat/${service.id}`)}
              className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 transition-colors"
            >
              <MessageSquare size={18} />
              <span>Review & Chat</span>
            </button>
          </div>
        ))}
      </div>

      {mockServices.length === 0 && (
        <div className="text-center py-12">
          <p className="text-gray-500 mb-4">No services tracked yet</p>
          <button
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
