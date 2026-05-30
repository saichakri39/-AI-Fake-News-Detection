import React from "react";
import { useState } from "react";
import API from "../services/api";

function Home() {
  const [news, setNews] = useState("");
  const [result, setResult] = useState("");

  const detectNews = async () => {
    try {
      const response = await API.post("/predict", {
        text: news,
      });

      setResult(response.data.prediction);
    } catch (error) {
      console.log(error);
      setResult("Backend Error");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white p-5">
      <h1 className="text-4xl font-bold mb-6">
        AI Fake News Detection
      </h1>

      <textarea
        rows="8"
        className="w-full max-w-2xl p-4 text-black rounded-lg"
        placeholder="Enter news here..."
        value={news}
        onChange={(e) => setNews(e.target.value)}
      />

      <button
        onClick={detectNews}
        className="mt-4 px-6 py-3 bg-blue-600 rounded-lg"
      >
        Detect News
      </button>

      {result && (
        <h2 className="mt-6 text-2xl font-bold">
          Result: {result}
        </h2>
      )}
    </div>
  );
}

export default Home;