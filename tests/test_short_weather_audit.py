import unittest
import test_refresh_visual


class ShortWeatherAudit(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = test_refresh_visual.RefreshVisualTests.asyncSetUp
    asyncTearDown = test_refresh_visual.RefreshVisualTests.asyncTearDown

    async def test_weather_value_fits_short_shared_panel(self):
        await self.page.goto(self.url + '/presentation.html')
        await self.page.wait_for_function('typeof window.updateCore === "function"')
        for width, height in ((600, 268), (420, 300)):
            await self.page.set_viewport_size({'width': width, 'height': height})
            await self.page.evaluate('window.updateCore({kind:"weather", title:"CLIMA", city:"Porto Alegre", temperature:19, condition:"Nublado", rain:80, wind:12, humidity:70, reduced:true})')
            await self.page.wait_for_timeout(150)
            fact = await self.page.locator('.fact').bounding_box()
            metrics = await self.page.locator('#metrics').bounding_box()
            self.assertLessEqual(fact['y'] + fact['height'], height)
            self.assertLessEqual(metrics['y'] + metrics['height'], height)
            self.assertEqual(self.errors, [])
