import "dotenv/config";
export const OPENAI_API_KEY = process.env.OPENAI_API_KEY;
export const PORT = Number(process.env.PORT ?? 3000);
if (!OPENAI_API_KEY) throw new Error("OPENAI_API_KEY missing");
