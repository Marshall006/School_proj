// Metro doit pouvoir remonter au dossier `shared/` : le protocole de
// deverrouillage est partage avec l'API et le tableau de bord.
const http = require("http");
const path = require("path");
const { getDefaultConfig } = require("expo/metro-config");

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, "..");

const config = getDefaultConfig(projectRoot);

config.watchFolders = [path.resolve(workspaceRoot, "shared")];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, "node_modules"),
  path.resolve(workspaceRoot, "node_modules"),
];
config.resolver.extraNodeModules = {
  "@koda/shared": path.resolve(workspaceRoot, "shared/src"),
};

// Les modules ESM en TypeScript importent leurs voisins avec l'extension
// `.js` (exigence de Node). Metro ne fait pas cette correspondance vers le
// `.ts` correspondant : on l'ajoute ici pour que le meme code source serve a
// Node, a Next.js et a React Native.
const defaultResolveRequest = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (moduleName.startsWith(".") && moduleName.endsWith(".js")) {
    try {
      return context.resolveRequest(context, moduleName.slice(0, -3), platform);
    } catch {
      // Le fichier .js existe reellement : on laisse la resolution standard.
    }
  }
  return (defaultResolveRequest ?? context.resolveRequest)(context, moduleName, platform);
};

// Relais de l'API a travers le serveur de developpement.
//
// Un telephone ne joint pas forcement la machine de developpement sur le port
// de l'API : sous WSL l'adresse de la VM Linux est invisible du reseau local,
// et en mode tunnel seul le port de Metro est expose. En relayant `/api/*`
// vers l'API locale, le telephone n'a qu'une adresse a joindre — celle qui lui
// sert deja le bundle — quel que soit le mode (LAN, tunnel, simulateur).
const API_TARGET = new URL(process.env.KODA_API_PROXY_TARGET || "http://127.0.0.1:8000");

function proxyToApi(req, res) {
  const upstream = http.request(
    {
      hostname: API_TARGET.hostname,
      port: API_TARGET.port || 80,
      path: req.url,
      method: req.method,
      headers: { ...req.headers, host: API_TARGET.host },
    },
    (apiResponse) => {
      res.writeHead(apiResponse.statusCode || 502, apiResponse.headers);
      apiResponse.pipe(res);
    },
  );
  upstream.on("error", () => {
    if (!res.headersSent) {
      res.writeHead(502, { "Content-Type": "application/json" });
    }
    // Meme format d'erreur que l'API : l'application affiche le message tel quel.
    res.end(
      JSON.stringify({
        error: {
          code: "api_unreachable",
          message: `L'API KODA ne repond pas (${API_TARGET.origin}). Lancez \`make api\` sur l'ordinateur.`,
          details: {},
        },
      }),
    );
  });
  req.pipe(upstream);
}

const previousEnhanceMiddleware = config.server.enhanceMiddleware;
config.server.enhanceMiddleware = (metroMiddleware, server) => {
  const next = previousEnhanceMiddleware
    ? previousEnhanceMiddleware(metroMiddleware, server)
    : metroMiddleware;
  return (req, res, fallthrough) => {
    if (req.url && req.url.startsWith("/api/")) {
      proxyToApi(req, res);
      return;
    }
    next(req, res, fallthrough);
  };
};

module.exports = config;
