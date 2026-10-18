"""Isolated provider environment for a bounded research job."""
import asyncio
import json
import sys


async def main():
    from gpt_researcher import GPTResearcher
    worker = GPTResearcher(query=sys.argv[1], report_type='research_report')
    await worker.conduct_research()
    report = await worker.write_report()
    print('JARVIS_REPORT:'+json.dumps({'ok':True,'report':report[:30000], 'complete':len(report)<=30000,'data_is_untrusted':True}),flush=True)


if __name__ == '__main__':
    asyncio.run(main())
