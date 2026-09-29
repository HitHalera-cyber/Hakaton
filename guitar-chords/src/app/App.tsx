import { AboutDialog, UpdateBanner } from '../features/about/Updates';
import { ChordDisplay } from '../features/chord/ChordDisplay';
import { AppProvider, useApp } from './AppContext';
import { BoardCard } from './layout/BoardCard';
import { Sidebar } from './layout/Sidebar';
import { TopBar } from './layout/TopBar';
import { ALL_TABS } from './navigation';
import { ToolPanel } from './panels';

function Shell() {
  const app = useApp();
  const { settings, guitar } = app;
  const tab = settings.view.tab;
  const current = ALL_TABS.find((t) => t.id === tab)!;

  return (
    <div className="app">
      <Sidebar
        tab={tab}
        onTab={app.openTab}
        onAbout={() => app.setAboutOpen(true)}
        badges={{ sequence: app.sequencer.playing ? '▶' : undefined, listen: app.listener.active ? '●' : undefined }}
      />
      <div className="main">
        <UpdateBanner status={app.updates.status} />
        <TopBar />
        <main className="workspace">
          <BoardCard />
          <ChordDisplay
            result={guitar.result}
            soundingMidi={guitar.activeMidi}
            source={guitar.source}
            capo={guitar.capo}
            shapeSymbol={guitar.shapeSymbol}
            warnings={guitar.source === 'board' ? guitar.fingering.warnings : []}
            onPlay={guitar.play}
            onSave={app.collections.save}
            onAddToSequence={app.addCurrentToSequence}
            onShowVoicings={guitar.chordRef ? () => app.showVoicings(guitar.chordRef!) : undefined}
            onExport={app.exports.exportChord}
          />
          <section className="panel tools">
            <h2 className="tool-title">
              <span>{current.icon}</span> {current.label}
            </h2>
            <ToolPanel tab={tab} />
          </section>
        </main>
      </div>
      {app.toast && <div className="toast">{app.toast}</div>}
      {app.aboutOpen && <AboutDialog info={app.updates.info} status={app.updates.status} onClose={() => app.setAboutOpen(false)} />}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Shell />
    </AppProvider>
  );
}
