// Реестр модулей. Порядок здесь — порядок в меню внутри группы.

import { changesModule } from './changes';
import { circleModule } from './circle';
import { favoritesModule } from './favorites';
import { fingercheckModule } from './fingercheck';
import type { ModuleId } from './ids';
import { keyModule } from './key';
import { lessonsModule } from './lessons';
import { libraryModule } from './library';
import { listenModule } from './listen';
import { melodyModule } from './melody';
import { metronomeModule } from './metronome';
import { midiModule } from './midi';
import { rhythmModule } from './rhythm';
import { scalesModule } from './scales';
import { sequenceModule } from './sequence';
import { songModule } from './song';
import { songbookModule } from './songbook';
import { soundModule } from './sound';
import { statsModule } from './stats';
import { trainerModule } from './trainer';
import { tunerModule } from './tuner';
import { GROUPS, type ModuleDef } from './types';

export const MODULES: ModuleDef[] = [
  listenModule,
  songbookModule,
  songModule,
  melodyModule,
  circleModule,
  sequenceModule,
  soundModule,
  metronomeModule,
  lessonsModule,
  changesModule,
  rhythmModule,
  fingercheckModule,
  trainerModule,
  statsModule,
  libraryModule,
  scalesModule,
  keyModule,
  tunerModule,
  midiModule,
  favoritesModule,
];

const BY_ID = new Map(MODULES.map((m) => [m.id, m]));

export const getModule = (id: ModuleId): ModuleDef => BY_ID.get(id) ?? MODULES[0];

export const MODULE_GROUPS = GROUPS.map((g) => ({ ...g, modules: MODULES.filter((m) => m.group === g.id) }));
