import express from 'express';
import path from 'path';
import dotenv from 'dotenv';
import { createServer as createViteServer } from 'vite';
import { GoogleGenAI, Type } from '@google/genai';

// Initialize env vars
dotenv.config();

const isProd = process.env.NODE_ENV === 'production';
const PORT = 3000;

async function bootstrap() {
  const app = express();
  app.use(express.json());

  // API Route: Anonymization NER Pipeline
  app.post('/api/anonymize', async (req, res) => {
    const { rawText } = req.body;
    if (!rawText) {
      return res.status(400).json({ error: 'Text prompt parameters missing.' });
    }

    const apiKey = process.env.GEMINI_API_KEY;
    // Check if key is available. If missing or default placeholder, signal auth requirement
    if (!apiKey || apiKey === 'MY_GEMINI_API_KEY' || apiKey === '') {
      return res.status(401).json({ error: 'GEMINI_API_KEY required' });
    }

    try {
      // Connect to Google Gemini API
      const ai = new GoogleGenAI({
        apiKey,
        httpOptions: {
          headers: {
            'User-Agent': 'aistudio-build'
          }
        }
      });

      // Instruct Gemini to parse unstructured narrative and output highly secure de-identified results
      const response = await ai.models.generateContent({
        model: 'gemini-3.5-flash',
        contents: `Analyze this unstructured mortality report and strip all Personally Identifiable Information (PII) to ensure spatial and administrative anonymity.
Report to process: "${rawText}"

Identify direct PII (such as full names, precise ages, clock times, family relationship details, and exact dwelling numbers) that should be discarded and record them in 'recordsDiscarded' list.
Flag sensitive words that should be redacted from the original text in the 'piiFlagged' array (each with their word and category label).
For geolocating, determine a generalized street intersection or neighborhood block centroid in San Francisco (never the exact door number) and return approximated latitude/longitude.
Group the age safely into rigid groups: '<18', '18-24', '25-34', '35-44', '45-54', '55-64', '65-74', '75-84'.
Determine manner of death of either 'Natural', 'Accident', 'Toxicological', or 'Environmental'.

Conform your output to the required JSON schema response.`,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              originalText: { type: Type.STRING },
              piiFlagged: {
                type: Type.ARRAY,
                items: {
                  type: Type.OBJECT,
                  properties: {
                    word: { type: Type.STRING },
                    category: { type: Type.STRING }
                  },
                  required: ['word', 'category']
                }
              },
              recordsDiscarded: {
                type: Type.ARRAY,
                items: { type: Type.STRING }
              },
              demographicsExtracted: {
                type: Type.OBJECT,
                properties: {
                  ageGroup: { type: Type.STRING },
                  gender: { type: Type.STRING },
                  manner: { type: Type.STRING }
                },
                required: ['ageGroup', 'gender', 'manner']
              },
              spatialAggregation: {
                type: Type.OBJECT,
                properties: {
                  entity: { type: Type.STRING },
                  lat: { type: Type.NUMBER },
                  lng: { type: Type.NUMBER },
                  type: { type: Type.STRING }
                },
                required: ['entity', 'lat', 'lng', 'type']
              },
              rawGeoJson: { type: Type.STRING, description: "A valid, pretty stringified GeoJSON Feature representing the aggregated point" }
            },
            required: ['originalText', 'piiFlagged', 'recordsDiscarded', 'demographicsExtracted', 'spatialAggregation', 'rawGeoJson']
          }
        }
      });

      const responseText = response.text;
      if (!responseText) {
        throw new Error('Empety AI response returned.');
      }

      const parsedResult = JSON.parse(responseText.trim());
      res.json(parsedResult);
    } catch (error: any) {
      console.error('Server-side processing pipeline error:', error);
      res.status(500).json({ error: 'AI processing failed', details: error.message });
    }
  });

  // Serve Frontend assets using Vite or Express static depends on NODE_ENV
  if (!isProd) {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`Server launched on http://0.0.0.0:${PORT} (ENV: ${isProd ? 'Production' : 'Development'})`);
  });
}

bootstrap();
