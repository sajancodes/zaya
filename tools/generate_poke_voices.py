"""Generate each configured Nika reaction once; playback never calls AI."""
import asyncio
import argparse
import wave
from core.notification_voice import synthesize_notice
from core.zayabar_config import CONFIG_PATH, load_config, local_path


async def generate(config_path=CONFIG_PATH, overwrite=False):
    config = load_config(config_path)
    for reaction in config['poke_reactions']:
        target = local_path(reaction.get('audio', ''), config_path)
        if not target:
            continue
        if target.is_file() and not overwrite:
            print(f'Already saved: {target.name}')
            continue
        audio, _transcript = await synthesize_notice(reaction['text'], verbatim=True)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix('.tmp')
        with wave.open(str(temporary), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(24000)
            stream.writeframes(audio)
        temporary.replace(target)
        print(f'Saved Nika reaction: {target.name}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    asyncio.run(generate(overwrite=args.overwrite))
