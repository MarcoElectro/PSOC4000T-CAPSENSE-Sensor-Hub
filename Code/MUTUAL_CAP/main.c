/*******************************************************************************
* File Name:   main.c
*
* Description: Source code for the mutual capacitance sensor setup
* Changes on the sensors need to be done using CAPSENSE Configurator
* and then re-program the board, so that the sensor context is updated
*
*
*
*******************************************************************************
* Copyright 2024, Cypress Semiconductor Corporation (an Infineon company) or
* an affiliate of Cypress Semiconductor Corporation.  All rights reserved.
*
* This software, including source code, documentation and related
* materials ("Software") is owned by Cypress Semiconductor Corporation
* or one of its affiliates ("Cypress") and is protected by and subject to
* worldwide patent protection (United States and foreign),
* United States copyright laws and international treaty provisions.
* Therefore, you may use this Software only as provided in the license
* agreement accompanying the software package from which you
* obtained this Software ("EULA").
* If no EULA applies, Cypress hereby grants you a personal, non-exclusive,
* non-transferable license to copy, modify, and compile the Software
* source code solely for use in connection with Cypress's
* integrated circuit products.  Any reproduction, modification, translation,
* compilation, or representation of this Software except as specified
* above is prohibited without the express written permission of Cypress.
*
* Disclaimer: THIS SOFTWARE IS PROVIDED AS-IS, WITH NO WARRANTY OF ANY KIND,
* EXPRESS OR IMPLIED, INCLUDING, BUT NOT LIMITED TO, NONINFRINGEMENT, IMPLIED
* WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. Cypress
* reserves the right to make changes to the Software without notice. Cypress does
* not assume any liability arising out of the application or use of the
* Software or any product or circuit described in the Software. Cypress does
* not authorize its products for use in any products where a malfunction or
* failure of the Cypress product may reasonably be expected to result in
* significant property damage, injury or death ("High Risk Product"). By
* including Cypress's product in a High Risk Product, the manufacturer
* of such system or application assumes all risk of such use and in doing
* so agrees to indemnify Cypress against all liability.
*******************************************************************************/


/*******************************************************************************
* Header Files
*******************************************************************************/
#include "cy_capsense_structure.h"
#include "cy_pdl.h"
#include "cybsp.h"
#include "cycfg.h"
#include "cycfg_capsense.h"
#include <stdio.h>

//#include "cy_retarget_io.h"
// Update NUM_OF_SENSORS to match your actual sensor count (can also be checked with cy_capsense_tuner.sensorContext size)
#define NUM_OF_SENSORS (sizeof(cy_capsense_tuner.sensorContext) / sizeof(cy_capsense_tuner.sensorContext[0]))

// Struct for storing the capsense values for sending it over I2C
struct
{
	uint16_t rawcount[NUM_OF_SENSORS];
	uint16_t diffcount[NUM_OF_SENSORS];
	uint16_t baseline[NUM_OF_SENSORS];
}capsense_data;







cy_stc_scb_ezi2c_context_t ezi2c_context;
/*******************************************************************************
* Function Name: capsense_msc0_isr
********************************************************************************
* Summary:
*  Wrapper function for handling interrupts from CAPSENSE MSC0 block.
*
*******************************************************************************/
static void capsense_msc0_isr(void)
{
    Cy_CapSense_InterruptHandler(CY_MSCLP0_HW, &cy_capsense_context);
}

/*******************************************************************************
* Function Name: ezi2c_isr
********************************************************************************
* Summary:
* Wrapper function for handling interrupts from EZI2C block.
*
*******************************************************************************/
static void ezi2c_isr(void)
{
    Cy_SCB_EZI2C_Interrupt(EZI2C_HW, &ezi2c_context);
}



int main(void)
{
    cy_rslt_t result;
    uint32_t cnt = 0;
	char uart_buffer[200];
    /* Initialize the device and board peripherals */
    result = cybsp_init() ;
    if (result != CY_RSLT_SUCCESS)
    {

    }

	/* Enable global interrupts */
	__enable_irq();

    cy_capsense_status_t status = CY_CAPSENSE_STATUS_SUCCESS;

    Cy_SCB_UART_Init(UART_HW, &UART_config, NULL);
    Cy_SCB_UART_Enable(UART_HW);
//    cy_retarget_io_init(UART_HW);
	
//    printf("Started");


	/* CAPSENSE interrupt configuration MSC 0 */
	const cy_stc_sysint_t capsense_msc0_interrupt_config =
	{
		.intrSrc = CY_MSCLP0_LP_IRQ,
		.intrPriority = 0x03,
	};

	/* Capture the MSC HW block and initialize it to the default state. */
	status = Cy_CapSense_Init(&cy_capsense_context);

	if (CY_CAPSENSE_STATUS_SUCCESS == status)
	{
		/* Initialize CAPSENSE interrupt for MSC 0 */
		Cy_SysInt_Init(&capsense_msc0_interrupt_config, capsense_msc0_isr);
		NVIC_ClearPendingIRQ(capsense_msc0_interrupt_config.intrSrc);
		NVIC_EnableIRQ(capsense_msc0_interrupt_config.intrSrc);

		/* Initialize the CAPSENSE firmware modules. */
		status = Cy_CapSense_Enable(&cy_capsense_context);
	}


	/* EZI2C interrupt configuration structure */
	const cy_stc_sysint_t ezi2c_intr_config =
	{
		.intrSrc = EZI2C_IRQ,
		.intrPriority = 0x03,
	};

	/* Initialize the EzI2C firmware module */
	status = Cy_SCB_EZI2C_Init(EZI2C_HW, &EZI2C_config, &ezi2c_context);

	if(status != CY_SCB_EZI2C_SUCCESS)
	{
		while(1);
	}

	Cy_SysInt_Init(&ezi2c_intr_config, ezi2c_isr);
	NVIC_EnableIRQ(ezi2c_intr_config.intrSrc);

	/* Set the CAPSENSE data structure as the I2C buffer to be exposed to the
	 * master on primary slave address interface. Any I2C host tools such as
	 * the Tuner or the Bridge Control Panel can read this buffer but you can
	 * connect only one tool at a time.
	 * Address of this Buffer is 0x08
	 */
	Cy_SCB_EZI2C_SetBuffer1(EZI2C_HW, (uint8_t *)&cy_capsense_tuner,
							sizeof(cy_capsense_tuner), sizeof(cy_capsense_tuner),
							&ezi2c_context);
    
    /* Set up the secondary buffer for our custom data structure
     * so it can be read by another MCU via I2C
     * Address of this Buffer is 0x09
     * Can be accessed with a normal I2C read command
     */
    Cy_SCB_EZI2C_SetBuffer2(EZI2C_HW, (uint8_t *)&capsense_data,
                            sizeof(capsense_data), sizeof(capsense_data),
                            &ezi2c_context);

    // Enable the I2C
	Cy_SCB_EZI2C_Enable(EZI2C_HW);



    /* Start the first scan */
	Cy_CapSense_ScanAllSlots(&cy_capsense_context);

	for (;;)
	{
		if(CY_CAPSENSE_NOT_BUSY == Cy_CapSense_IsBusy(&cy_capsense_context))
		{
			/* Process all widgets */
			Cy_CapSense_ProcessAllWidgets(&cy_capsense_context);

            /* Store raw counts and diff counts for each sensor */
            for(uint32_t i = 0; i < NUM_OF_SENSORS; i++)
            {
                /* Get raw counts and diff counts from all sensors from the sensor context */
                capsense_data.rawcount[i] = cy_capsense_tuner.sensorContext[i].raw;
                capsense_data.diffcount[i] = cy_capsense_tuner.sensorContext[i].diff;
                capsense_data.baseline[i] = cy_capsense_tuner.sensorContext[i].bsln;
                //printf("RAWcount_[%d] content: %u | Diffcount_[%d] content: %u \r\n", i, capsense_data.rawcount[i], i, capsense_data.diffcount[i]);
            }

			/* Establishes synchronized communication with the CAPSENSE Tuner tool */
			Cy_CapSense_RunTuner(&cy_capsense_context);

			/* Start the next scan */
			Cy_CapSense_ScanAllSlots(&cy_capsense_context);

			cnt++;
			if(cnt >= 100)
			{
				cnt = 0;
//				Cy_GPIO_Inv(USER_LED_PORT, USER_LED_PIN);

				// In case you want to access the sensor values over UART, you can also use printf
                for(uint32_t i = 0; i < NUM_OF_SENSORS; i++)
                {
                    sprintf(uart_buffer, "RAWcount_[%lu] content: %u | Diffcount_[%lu] content: %u\r\n", 
                            i, capsense_data.rawcount[i], i, capsense_data.diffcount[i]);
                    Cy_SCB_UART_PutString(UART_HW, uart_buffer);
                }

                /* Send separator line */
                Cy_SCB_UART_PutString(UART_HW, "---\r\n");
			
			}
		}
	}
}

