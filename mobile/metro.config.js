// Metro doit pouvoir remonter au dossier `shared/` : le protocole de
// deverrouillage est partage avec l'API et le tableau de bord.
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

module.exports = config;
