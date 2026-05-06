import { useState } from "react";
import { useNavigate, useLocation } from "react-router";
import { Link, Upload as UploadIcon, FileText } from "lucide-react";

type UploadLocationState = {
  serviceName?: string;
  url?: string;
};

export function Upload() {
  const navigate = useNavigate();
  const location = useLocation();
  const prefill = (location.state as UploadLocationState | null) ?? {};
  const isUpdate = Boolean(prefill.serviceName);
  // const [activeTab, setActiveTab] = useState<"link" | "text" >("link");
  const [serviceName, setServiceName] = useState(prefill.serviceName ?? "");
  const [url, setUrl] = useState(prefill.url ?? "");
  const [tosText, setTosText] = useState("");
  // const [file, setFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // if (activeTab === "file" && !file) {
    //   alert("Please select a file before submitting.");
    //   return;
    // }

    setSubmitting(true);

    try {
      const formData = new FormData();
      formData.append("chatbot_name", serviceName);
      // formData.append("activeTab", activeTab);
      formData.append("website_url", url);
      formData.append("current_tos", tosText);
      // if (activeTab === "link") {
      //   formData.append("url", url);
      // } else if (activeTab === "text") {
      //   formData.append("tosText", tosText);
      // } 
      let payload = {"chatbot_name": serviceName, "website_url": url, "current_tos": tosText};

      const response = await fetch("/api/tos-history", {
        method: "POST",
        body: JSON.stringify(payload),
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText || "Upload failed");
      }

      const result = await response.json();
      console.log("Backend response:", result);

      navigate("/dashboard");
    } catch (error) {
      console.error(error);
      alert("There was an error submitting the form. Check the console for details.");
    } finally {
      setSubmitting(false);
    }
  };

  // const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
  //   if (e.target.files && e.target.files[0]) {
  //     setFile(e.target.files[0]);
  //   }
  // };

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-semibold text-gray-900 mb-2">
          {isUpdate ? `Update ToS for ${prefill.serviceName}` : "Add New ToS"}
        </h1>
        <p className="text-gray-600">
          {isUpdate
            ? "Paste the latest version. We'll compare it against the previous one."
            : "Upload or link a Terms of Service document to track"}
        </p>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="mb-6">
          <label htmlFor="serviceName" className="block text-sm text-gray-700 mb-2">
            Service Name
          </label>
          <input
            id="serviceName"
            type="text"
            value={serviceName}
            onChange={(e) => setServiceName(e.target.value)}
            placeholder="e.g., Google, Facebook, Amazon"
            className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            required
          />
        </div>

        <div className="mb-6">
          <div className="flex gap-2 border-b border-gray-200">
            {/* <button
              onClick={() => setActiveTab("link")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "link"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              <Link size={18} />
              <span>Link</span>
            </button>
            <button
              onClick={() => setActiveTab("text")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "text"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              <FileText size={18} />
              <span>Paste Text</span>
            </button> */}
            {/* <button
              onClick={() => setActiveTab("file")}
              className={`flex items-center gap-2 px-4 py-2 border-b-2 transition-colors ${
                activeTab === "file"
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-600 hover:text-gray-900"
              }`}
            >
              <UploadIcon size={18} />
              <span>Upload File</span>
            </button> */}
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="mb-6">
            <label htmlFor="url" className="block text-sm text-gray-700 mb-2">
              ToS URL
            </label>
            <input
              id="url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/terms"
              className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              required
            />
          </div>
          <div className="mb-6">
              <label htmlFor="tosText" className="block text-sm text-gray-700 mb-2">
                ToS Content
              </label>
              <textarea
                id="tosText"
                value={tosText}
                onChange={(e) => setTosText(e.target.value)}
                placeholder="Paste the Terms of Service content here..."
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[300px] font-mono text-sm"
                required
              />
            </div>
          {/* {activeTab === "link" && (
            <div className="mb-6">
              <label htmlFor="url" className="block text-sm text-gray-700 mb-2">
                ToS URL
              </label>
              <input
                id="url"
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://example.com/terms"
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <p className="text-xs text-gray-500 mt-2">
                We'll fetch and analyze the Terms of Service from this URL
              </p>
            </div>
          )} */}

          {/* {activeTab === "text" && (
            <div className="mb-6">
              <label htmlFor="tosText" className="block text-sm text-gray-700 mb-2">
                ToS Content
              </label>
              <textarea
                id="tosText"
                value={tosText}
                onChange={(e) => setTosText(e.target.value)}
                placeholder="Paste the Terms of Service content here..."
                className="w-full px-4 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 min-h-[300px] font-mono text-sm"
                required
              />
            </div>
          )} */}

          {/* {activeTab === "file" && (
            <div className="mb-6">
              <label htmlFor="file" className="block text-sm text-gray-700 mb-2">
                Upload Document
              </label>
              <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 transition-colors">
                <input
                  id="file"
                  type="file"
                  onChange={handleFileChange}
                  accept=".txt,.pdf,.doc,.docx"
                  className="hidden"
                />
                <label
                  htmlFor="file"
                  className="cursor-pointer flex flex-col items-center gap-2"
                >
                  <UploadIcon size={48} className="text-gray-400" />
                  {file ? (
                    <p className="text-sm text-gray-700">{file.name}</p>
                  ) : (
                    <>
                      <p className="text-sm text-gray-600">
                        Click to upload or drag and drop
                      </p>
                      <p className="text-xs text-gray-500">
                        TXT, PDF, DOC, or DOCX (max 10MB)
                      </p>
                    </>
                  )}
                </label>
              </div>
            </div>
          )} */}

          <div className="flex gap-4">
            <button
              type="submit"
              className="flex-1 bg-blue-600 text-white py-3 px-6 rounded-md hover:bg-blue-700 transition-colors"
            >
              Analyze ToS
            </button>
            <button
              type="button"
              onClick={() => navigate("/dashboard")}
              className="px-6 py-3 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
