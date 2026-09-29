import { SessionProvider } from './api/useSession';
import { WorkspaceProvider } from './api/useWorkspace';
import { Frame } from './frame/Frame';
import { AppRoutes } from './routes';

export default function App() {
  return (
    <SessionProvider>
      <WorkspaceProvider>
        <Frame>
          <AppRoutes />
        </Frame>
      </WorkspaceProvider>
    </SessionProvider>
  );
}
