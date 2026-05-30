import axios from "axios";

const API = axios.create({
  baseURL: "https://saichakri.pythonanywhere.com",
});

export default API;